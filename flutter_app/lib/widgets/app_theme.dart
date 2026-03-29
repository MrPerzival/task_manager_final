// lib/widgets/app_theme.dart
import 'package:flutter/material.dart';

class AppTheme {
  AppTheme._();

  static const Color primary    = Color(0xFF6366F1);
  static const Color primaryDark= Color(0xFF4F46E5);
  static const Color surface    = Color(0xFF1E1E2E);
  static const Color surfaceVar = Color(0xFF27273A);
  static const Color onSurface  = Color(0xFFE2E8F0);
  static const Color subtle     = Color(0xFF94A3B8);
  static const Color error      = Color(0xFFEF4444);
  static const Color success    = Color(0xFF10B981);
  static const Color warning    = Color(0xFFF59E0B);

  static Color statusColor(String status) {
    switch (status) {
      case 'Done':        return success;
      case 'In Progress': return warning;
      default:            return primary;
    }
  }

  static Color statusBackground(String status) {
    switch (status) {
      case 'Done':        return success.withOpacity(0.12);
      case 'In Progress': return warning.withOpacity(0.12);
      default:            return primary.withOpacity(0.12);
    }
  }

  static ThemeData get dark => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: ColorScheme.dark(
      primary: primary, onPrimary: Colors.white,
      surface: surface, onSurface: onSurface,
      error: error,
    ),
    scaffoldBackgroundColor: surface,
    cardColor: surfaceVar,
    appBarTheme: const AppBarTheme(
      backgroundColor: surface, foregroundColor: onSurface,
      elevation: 0, centerTitle: false,
      titleTextStyle: TextStyle(
        fontSize: 20, fontWeight: FontWeight.w700,
        color: onSurface, letterSpacing: -0.3,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true, fillColor: surfaceVar,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: Colors.white.withOpacity(0.08)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: Colors.white.withOpacity(0.08)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: primary, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: error),
      ),
      labelStyle: const TextStyle(color: subtle),
      hintStyle: TextStyle(color: subtle.withOpacity(0.6)),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: primary, foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: primary),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: surfaceVar,
      selectedColor: primary.withOpacity(0.2),
      labelStyle: const TextStyle(fontSize: 12, color: onSurface),
      side: BorderSide(color: Colors.white.withOpacity(0.08)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    ),
    dividerColor: Colors.white.withOpacity(0.06),
  );
}
