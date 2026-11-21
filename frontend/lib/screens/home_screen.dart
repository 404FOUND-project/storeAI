import 'package:flutter/material.dart';

import '../app.dart' show ink;
import '../widgets/backend_state.dart';

class HomeScreen extends StatelessWidget {
  final ValueChanged<int> onNavigate;

  const HomeScreen({super.key, required this.onNavigate});

  @override
  Widget build(BuildContext context) => const Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        '홈',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      SizedBox(height: 18),
      BackendUnavailable(feature: '매출·운영 대시보드'),
    ],
  );
}
