// lib/services/api_service.dart
// HTTP client for the Task Manager backend.
// Change ApiConfig.baseUrl to your Render URL for production.

import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../models/task.dart';

// ── Config ────────────────────────────────────────────────────────────────────

class ApiConfig {
  /// ⚠️  UPDATE THIS for your environment:
  ///
  /// Local dev (iOS simulator / desktop):
  ///   static const String baseUrl = 'http://127.0.0.1:8000';
  ///
  /// Local dev (Android emulator):
  ///   static const String baseUrl = 'http://10.0.2.2:8000';
  ///
  /// Local dev (physical device — use your machine's LAN IP):
  ///   static const String baseUrl = 'http://192.168.x.x:8000';
  ///
  /// Production (Render):
  ///   static const String baseUrl = 'https://task-manager-api.onrender.com';
  static const String baseUrl = 'http://127.0.0.1:8000';

  static const Duration readTimeout  = Duration(seconds: 15);
  static const Duration writeTimeout = Duration(seconds: 30); // covers 2s backend delay
  static const int maxRetries = 2;
}

// ── Exception ─────────────────────────────────────────────────────────────────

class ApiException implements Exception {
  final int statusCode;
  final String message;

  const ApiException({required this.statusCode, required this.message});

  bool get isClientError => statusCode >= 400 && statusCode < 500;
  bool get isServerError => statusCode >= 500;

  String get userFacingMessage {
    if (statusCode == 0)   return 'Could not reach the server. Check your connection.';
    if (statusCode == 404) return message;
    if (statusCode == 422) return message;
    if (isServerError)     return 'Server error. Please try again later.';
    return message;
  }

  @override
  String toString() => 'ApiException($statusCode): $message';
}

// ── Service ───────────────────────────────────────────────────────────────────

class ApiService {
  static final http.Client _client = http.Client();

  static const Map<String, String> _headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  // Parses the v2 error envelope { "error": true, "detail": "..." }
  // and falls back to Pydantic validation list format.
  static ApiException _parseError(http.Response response) {
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final detail = body['detail'];
      String message;
      if (detail is String) {
        message = detail;
      } else if (detail is List) {
        message = detail
            .whereType<Map>()
            .map((e) => e['msg']?.toString() ?? '')
            .where((s) => s.isNotEmpty)
            .join('; ');
        if (message.isEmpty) message = 'Validation error.';
      } else {
        message = response.body;
      }
      return ApiException(statusCode: response.statusCode, message: message);
    } catch (_) {
      return ApiException(
        statusCode: response.statusCode,
        message: response.body.isEmpty ? 'HTTP ${response.statusCode}' : response.body,
      );
    }
  }

  // Retries on server errors / network hiccups; never retries 4xx.
  static Future<T> _withRetry<T>(Future<T> Function() fn) async {
    int attempts = 0;
    while (true) {
      try {
        return await fn();
      } on ApiException catch (e) {
        if (e.isClientError || attempts >= ApiConfig.maxRetries) rethrow;
        attempts++;
        await Future.delayed(Duration(milliseconds: 500 * attempts));
      } on SocketException catch (e) {
        if (attempts >= ApiConfig.maxRetries) {
          throw ApiException(statusCode: 0, message: 'Network error: ${e.message}');
        }
        attempts++;
        await Future.delayed(Duration(milliseconds: 500 * attempts));
      } catch (e) {
        throw ApiException(statusCode: 0, message: e.toString());
      }
    }
  }

  // ── GET /tasks ─────────────────────────────────────────────────────────────
  static Future<List<Task>> fetchTasks({String? status, String? search}) async {
    return _withRetry(() async {
      final params = <String, String>{};
      if (status != null && status.isNotEmpty) params['status'] = status;
      if (search != null && search.isNotEmpty)  params['search'] = search;

      final uri = Uri.parse('${ApiConfig.baseUrl}/tasks')
          .replace(queryParameters: params);

      final response = await _client
          .get(uri, headers: _headers)
          .timeout(ApiConfig.readTimeout);

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((e) => Task.fromJson(e as Map<String, dynamic>)).toList();
      }
      throw _parseError(response);
    });
  }

  // ── POST /tasks ────────────────────────────────────────────────────────────
  // No retry — POST is not idempotent; avoid duplicate inserts.
  static Future<Task> createTask(Task task) async {
    try {
      final response = await _client
          .post(
            Uri.parse('${ApiConfig.baseUrl}/tasks'),
            headers: _headers,
            body: jsonEncode(task.toJson()),
          )
          .timeout(ApiConfig.writeTimeout);

      if (response.statusCode == 201) {
        return Task.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
      }
      throw _parseError(response);
    } on ApiException {
      rethrow;
    } on SocketException catch (e) {
      throw ApiException(statusCode: 0, message: 'Network error: ${e.message}');
    } catch (e) {
      throw ApiException(statusCode: 0, message: e.toString());
    }
  }

  // ── PUT /tasks/{id} ────────────────────────────────────────────────────────
  static Future<Task> updateTask(Task task) async {
    return _withRetry(() async {
      final response = await _client
          .put(
            Uri.parse('${ApiConfig.baseUrl}/tasks/${task.id}'),
            headers: _headers,
            body: jsonEncode(task.toJson()),
          )
          .timeout(ApiConfig.writeTimeout);

      if (response.statusCode == 200) {
        return Task.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
      }
      throw _parseError(response);
    });
  }

  // ── DELETE /tasks/{id} ────────────────────────────────────────────────────
  static Future<void> deleteTask(int id) async {
    return _withRetry(() async {
      final response = await _client
          .delete(
            Uri.parse('${ApiConfig.baseUrl}/tasks/$id'),
            headers: _headers,
          )
          .timeout(ApiConfig.readTimeout);

      if (response.statusCode == 204) return;
      throw _parseError(response);
    });
  }

  // ── Health check ──────────────────────────────────────────────────────────
  static Future<bool> isReachable() async {
    try {
      final response = await _client
          .get(Uri.parse('${ApiConfig.baseUrl}/'), headers: _headers)
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
