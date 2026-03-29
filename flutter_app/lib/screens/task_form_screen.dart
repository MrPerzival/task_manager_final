// lib/screens/task_form_screen.dart
// Task creation & editing form.
// Features:
//  • All required fields with validation
//  • Draft auto-save on every change (SharedPreferences)
//  • Draft restored on screen open with dialog prompt
//  • 2-second async save with loading indicator + disabled Save button
//  • Blocked-by dropdown excluding self

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../models/task.dart';
import '../services/task_provider.dart';
import '../services/draft_service.dart';
import '../services/api_service.dart';
import '../widgets/app_theme.dart';

class TaskFormScreen extends StatefulWidget {
  final Task? existingTask;
  const TaskFormScreen({super.key, this.existingTask});
  bool get isNew => existingTask == null;

  @override
  State<TaskFormScreen> createState() => _TaskFormScreenState();
}

class _TaskFormScreenState extends State<TaskFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _titleCtrl;
  late final TextEditingController _descCtrl;

  DateTime? _dueDate;
  String    _status    = 'To-Do';
  int?      _blockedBy;
  String    _recurring = 'None';
  bool      _isSaving  = false;
  String?   _saveError;

  static const _statusOptions    = ['To-Do', 'In Progress', 'Done'];
  static const _recurringOptions = ['None', 'Daily', 'Weekly'];

  @override
  void initState() {
    super.initState();
    final t = widget.existingTask;
    _titleCtrl = TextEditingController(text: t?.title ?? '');
    _descCtrl  = TextEditingController(text: t?.description ?? '');
    _dueDate   = t?.dueDate;
    _status    = t?.status    ?? 'To-Do';
    _blockedBy = t?.blockedBy;
    _recurring = t?.recurring ?? 'None';

    _titleCtrl.addListener(_saveDraft);
    _descCtrl.addListener(_saveDraft);

    WidgetsBinding.instance.addPostFrameCallback((_) => _loadDraft());
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  // ── Draft persistence ─────────────────────────────────────────────────────

  Map<String, dynamic> get _draftData => {
    'title':       _titleCtrl.text,
    'description': _descCtrl.text,
    'due_date':    _dueDate?.toIso8601String(),
    'status':      _status,
    'blocked_by':  _blockedBy,
    'recurring':   _recurring,
  };

  Future<void> _saveDraft() async {
    if (_isSaving) return;
    await DraftService.saveDraft(
      isNew: widget.isNew,
      taskId: widget.existingTask?.id,
      data: _draftData,
    );
  }

  Future<void> _loadDraft() async {
    final draft = await DraftService.loadDraft(
      isNew: widget.isNew,
      taskId: widget.existingTask?.id,
    );
    if (draft == null || !mounted) return;

    final draftTitle = draft['title'] as String? ?? '';
    if (draftTitle.isNotEmpty && draftTitle != (widget.existingTask?.title ?? '')) {
      final restore = await _showRestoreDialog();
      if (!restore || !mounted) return;
      setState(() {
        _titleCtrl.text = draftTitle;
        _descCtrl.text  = draft['description'] as String? ?? '';
        final rawDate   = draft['due_date'] as String?;
        _dueDate        = rawDate != null ? DateTime.tryParse(rawDate) : null;
        _status         = draft['status']    as String? ?? 'To-Do';
        _blockedBy      = draft['blocked_by'] as int?;
        _recurring      = draft['recurring'] as String? ?? 'None';
      });
    }
  }

  Future<bool> _showRestoreDialog() async {
    return await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surfaceVar,
        title: const Text('Restore Draft?'),
        content: const Text(
          'You have unsaved changes from a previous session. Restore them?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Discard'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Restore'),
          ),
        ],
      ),
    ) ?? false;
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || _isSaving) return;

    setState(() { _isSaving = true; _saveError = null; });

    try {
      final task = Task(
        id:          widget.existingTask?.id ?? 0,
        title:       _titleCtrl.text.trim(),
        description: _descCtrl.text.trim(),
        dueDate:     _dueDate,
        status:      _status,
        blockedBy:   _blockedBy,
        recurring:   _recurring,
      );

      final provider = context.read<TaskProvider>();
      if (widget.isNew) {
        await provider.createTask(task);
      } else {
        await provider.updateTask(task);
      }

      await DraftService.clearDraft(
        isNew: widget.isNew,
        taskId: widget.existingTask?.id,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(widget.isNew ? 'Task created!' : 'Task updated!'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ));
        Navigator.pop(context);
      }
    } on ApiException catch (e) {
      setState(() { _saveError = e.userFacingMessage; _isSaving = false; });
    } catch (e) {
      setState(() { _saveError = e.toString(); _isSaving = false; });
    }
  }

  // ── Date picker ───────────────────────────────────────────────────────────

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
      builder: (ctx, child) => Theme(data: AppTheme.dark, child: child!),
    );
    if (picked != null) {
      setState(() => _dueDate = picked);
      _saveDraft();
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final allTasks = context.watch<TaskProvider>().allTasks;
    final blockable = allTasks
        .where((t) => t.id != (widget.existingTask?.id ?? -1))
        .toList();

    return PopScope(
      onPopInvoked: (_) => _saveDraft(),
      child: Scaffold(
        appBar: AppBar(
          title: Text(widget.isNew ? 'New Task' : 'Edit Task'),
          actions: [
            _isSaving
                ? const Padding(
                    padding: EdgeInsets.only(right: 16),
                    child: SizedBox(
                      width: 20, height: 20,
                      child: CircularProgressIndicator(
                        color: AppTheme.primary, strokeWidth: 2,
                      ),
                    ),
                  )
                : TextButton(
                    onPressed: _submit,
                    child: const Text(
                      'Save',
                      style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w600),
                    ),
                  ),
          ],
        ),
        body: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [

              // ── Error banner ───────────────────────────────────────────
              if (_saveError != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.error.withOpacity(0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 18),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _saveError!,
                          style: const TextStyle(color: AppTheme.error, fontSize: 13),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // ── Title ──────────────────────────────────────────────────
              const _Label('Title *'),
              const SizedBox(height: 6),
              TextFormField(
                controller: _titleCtrl,
                style: const TextStyle(color: AppTheme.onSurface),
                decoration: const InputDecoration(hintText: 'Enter task title'),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Title is required.' : null,
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 18),

              // ── Description ───────────────────────────────────────────
              const _Label('Description'),
              const SizedBox(height: 6),
              TextFormField(
                controller: _descCtrl,
                style: const TextStyle(color: AppTheme.onSurface),
                decoration: const InputDecoration(hintText: 'Optional description'),
                maxLines: 3,
                textInputAction: TextInputAction.newline,
              ),
              const SizedBox(height: 18),

              // ── Due Date ──────────────────────────────────────────────
              const _Label('Due Date'),
              const SizedBox(height: 6),
              GestureDetector(
                onTap: _pickDate,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceVar,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white.withOpacity(0.08)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.calendar_today_rounded,
                          size: 18, color: AppTheme.subtle),
                      const SizedBox(width: 10),
                      Text(
                        _dueDate != null
                            ? DateFormat('MMMM d, yyyy').format(_dueDate!)
                            : 'Select a date',
                        style: TextStyle(
                          color: _dueDate != null
                              ? AppTheme.onSurface
                              : AppTheme.subtle.withOpacity(0.6),
                        ),
                      ),
                      const Spacer(),
                      if (_dueDate != null)
                        GestureDetector(
                          onTap: () { setState(() => _dueDate = null); _saveDraft(); },
                          child: const Icon(Icons.clear_rounded,
                              size: 16, color: AppTheme.subtle),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 18),

              // ── Status ────────────────────────────────────────────────
              const _Label('Status'),
              const SizedBox(height: 6),
              _Dropdown<String>(
                value: _status,
                items: _statusOptions,
                label: (s) => s,
                onChanged: (v) { setState(() => _status = v!); _saveDraft(); },
              ),
              const SizedBox(height: 18),

              // ── Recurring ─────────────────────────────────────────────
              const _Label('Recurring'),
              const SizedBox(height: 6),
              _Dropdown<String>(
                value: _recurring,
                items: _recurringOptions,
                label: (s) => s,
                onChanged: (v) { setState(() => _recurring = v!); _saveDraft(); },
              ),
              const SizedBox(height: 18),

              // ── Blocked By ────────────────────────────────────────────
              const _Label('Blocked By'),
              const SizedBox(height: 6),
              _Dropdown<int?>(
                value: _blockedBy,
                items: [null, ...blockable.map((t) => t.id)],
                label: (id) {
                  if (id == null) return 'None';
                  final t = blockable.where((x) => x.id == id).firstOrNull;
                  return t != null ? '${t.title} (#${t.id})' : '#$id';
                },
                onChanged: (v) { setState(() => _blockedBy = v); _saveDraft(); },
              ),
              const SizedBox(height: 32),

              // ── Save button ───────────────────────────────────────────
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _isSaving ? null : _submit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isSaving
                        ? AppTheme.primary.withOpacity(0.5)
                        : AppTheme.primary,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  child: _isSaving
                      ? const SizedBox(
                          width: 22, height: 22,
                          child: CircularProgressIndicator(
                            color: Colors.white, strokeWidth: 2.5,
                          ),
                        )
                      : Text(
                          widget.isNew ? 'Create Task' : 'Update Task',
                          style: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w600,
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Reusable sub-widgets ──────────────────────────────────────────────────────

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);
  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 13, fontWeight: FontWeight.w500,
        color: AppTheme.subtle, letterSpacing: 0.2,
      ),
    );
  }
}

class _Dropdown<T> extends StatelessWidget {
  final T value;
  final List<T> items;
  final String Function(T) label;
  final void Function(T?) onChanged;

  const _Dropdown({
    required this.value,
    required this.items,
    required this.label,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: AppTheme.surfaceVar,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          value: value,
          dropdownColor: AppTheme.surfaceVar,
          style: const TextStyle(color: AppTheme.onSurface, fontSize: 14),
          icon: const Icon(Icons.expand_more_rounded, size: 20, color: AppTheme.subtle),
          isExpanded: true,
          onChanged: onChanged,
          items: items.map((item) => DropdownMenuItem<T>(
            value: item,
            child: Text(label(item), overflow: TextOverflow.ellipsis),
          )).toList(),
        ),
      ),
    );
  }
}
