// lib/services/task_provider.dart
// Central state container (ChangeNotifier).

import 'package:flutter/material.dart';
import '../models/task.dart';
import 'api_service.dart';

enum LoadState { idle, loading, error }

class TaskProvider extends ChangeNotifier {
  List<Task> _tasks    = [];
  LoadState  _loadState = LoadState.idle;
  String?    _error;
  String     _searchQuery  = '';
  String     _statusFilter = '';

  List<Task>  get tasks        => _filtered;
  List<Task>  get allTasks     => _tasks;
  LoadState   get loadState    => _loadState;
  String?     get error        => _error;
  String      get searchQuery  => _searchQuery;
  String      get statusFilter => _statusFilter;

  List<Task> get _filtered => _tasks.where((t) {
    final matchSearch = _searchQuery.isEmpty ||
        t.title.toLowerCase().contains(_searchQuery.toLowerCase());
    final matchStatus = _statusFilter.isEmpty || t.status == _statusFilter;
    return matchSearch && matchStatus;
  }).toList();

  void setSearch(String q) {
    _searchQuery = q;
    notifyListeners();
  }

  void setStatusFilter(String s) {
    _statusFilter = s;
    notifyListeners();
  }

  Future<void> loadTasks() async {
    _loadState = LoadState.loading;
    _error = null;
    notifyListeners();
    try {
      _tasks = await ApiService.fetchTasks();
      _loadState = LoadState.idle;
    } on ApiException catch (e) {
      _error = e.userFacingMessage;
      _loadState = LoadState.error;
    } catch (e) {
      _error = e.toString();
      _loadState = LoadState.error;
    }
    notifyListeners();
  }

  Future<Task> createTask(Task task) async {
    final created = await ApiService.createTask(task);
    await loadTasks();
    return created;
  }

  Future<Task> updateTask(Task task) async {
    final updated = await ApiService.updateTask(task);
    await loadTasks();
    return updated;
  }

  Future<void> deleteTask(int id) async {
    await ApiService.deleteTask(id);
    _tasks.removeWhere((t) => t.id == id);
    notifyListeners();
  }

  /// Returns true if [task] is visually blocked
  /// (its blocker exists and is not Done).
  bool isBlocked(Task task) {
    if (task.blockedBy == null) return false;
    final blocker = _tasks.where((t) => t.id == task.blockedBy).firstOrNull;
    if (blocker == null) return false;
    return !blocker.isDone;
  }
}
