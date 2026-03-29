// lib/widgets/connection_banner.dart
import 'package:flutter/material.dart';
import 'app_theme.dart';

class ConnectionBanner extends StatelessWidget {
  final String message;
  final bool isVisible;
  final VoidCallback? onRetry;

  const ConnectionBanner({
    super.key,
    required this.message,
    required this.isVisible,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOut,
      child: isVisible
          ? Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              color: AppTheme.error.withOpacity(0.12),
              child: Row(
                children: [
                  const Icon(Icons.wifi_off_rounded, size: 16, color: AppTheme.error),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      message,
                      style: const TextStyle(
                        color: AppTheme.error, fontSize: 13, fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  if (onRetry != null) ...[
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: onRetry,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppTheme.error.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text(
                          'Retry',
                          style: TextStyle(
                            color: AppTheme.error, fontSize: 12, fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            )
          : const SizedBox.shrink(),
    );
  }
}
