import 'package:flutter/material.dart';

import '../app.dart' show ink;
import '../widgets/backend_state.dart';

class AiAnalysisScreen extends StatelessWidget {
  const AiAnalysisScreen({super.key});

  @override
  Widget build(BuildContext context) => const Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'AI 운영 진단',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      SizedBox(height: 18),
      BackendUnavailable(feature: 'AI 운영 진단'),
    ],
  );
}
