import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, muted, line;

class BackendUnavailable extends StatelessWidget {
  final String feature;
  const BackendUnavailable({super.key, required this.feature});

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: line),
    ),
    child: Column(
      children: [
        const Icon(Icons.cloud_off_rounded, color: blue, size: 34),
        const SizedBox(height: 10),
        Text(
          '$feature 데이터를 불러올 수 없습니다',
          textAlign: TextAlign.center,
          style: const TextStyle(color: ink, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 6),
        const Text(
          '이 기능의 데이터를 제공하는 API가 준비되지 않았거나\n서버가 실행 중이지 않습니다.',
          textAlign: TextAlign.center,
          style: TextStyle(color: muted, fontSize: 11, height: 1.5),
        ),
      ],
    ),
  );
}
