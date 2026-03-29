// lib/services/draft_service.dart
// Persists form drafts to SharedPreferences so partially-filled forms
// survive navigation away.

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class DraftService {
  static const String _newKey = 'draft_task_new';
  static String _editKey(int id) => 'draft_task_$id';

  static Future<void> saveDraft({
    required bool isNew,
    int? taskId,
    required Map<String, dynamic> data,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(isNew ? _newKey : _editKey(taskId!), jsonEncode(data));
  }

  static Future<Map<String, dynamic>?> loadDraft({
    required bool isNew,
    int? taskId,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(isNew ? _newKey : _editKey(taskId!));
    if (raw == null) return null;
    try {
      return jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  static Future<void> clearDraft({required bool isNew, int? taskId}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(isNew ? _newKey : _editKey(taskId!));
  }
}
