import 'package:flutter/material.dart';

import '../app.dart' show ink;
import '../widgets/backend_state.dart';

class RecommendationScreen extends StatelessWidget {
  const RecommendationScreen({super.key});

  @override
  Widget build(BuildContext context) => const Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        '메뉴 추천',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      SizedBox(height: 18),
      BackendUnavailable(feature: '메뉴 추천'),
    ],
  );
}
