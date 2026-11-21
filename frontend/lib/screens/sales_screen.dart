import 'package:flutter/material.dart';

import '../app.dart' show ink;
import '../widgets/backend_state.dart';

class SalesScreen extends StatelessWidget {
  const SalesScreen({super.key});

  @override
  Widget build(BuildContext context) => const Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        '매출 분석',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      SizedBox(height: 18),
      BackendUnavailable(feature: '매출 분석'),
    ],
  );
}
