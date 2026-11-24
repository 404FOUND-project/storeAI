import 'package:flutter/material.dart';

import '../app.dart' show bg, ink;
import '../widgets/backend_state.dart';

class ReportScreen extends StatelessWidget {
  const ReportScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: bg,
    body: SafeArea(
      child: Column(
        children: [
          const SizedBox(height: 30),
          SizedBox(
            height: 54,
            child: Stack(
              alignment: Alignment.center,
              children: [
                const Text(
                  '운영 리포트',
                  style: TextStyle(
                    color: ink,
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Align(
                  alignment: Alignment.centerLeft,
                  child: IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(
                      Icons.chevron_left_rounded,
                      color: ink,
                      size: 30,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const Expanded(
            child: SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(18, 18, 18, 28),
              child: BackendUnavailable(feature: '운영 리포트'),
            ),
          ),
        ],
      ),
    ),
  );
}
