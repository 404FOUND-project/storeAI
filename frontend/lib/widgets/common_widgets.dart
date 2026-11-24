import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, muted, line, green;

// UI reused across screens.
Widget metric(
  String title,
  String value,
  String caption,
  IconData icon,
  Color color,
) => Container(
  padding: const EdgeInsets.all(15),
  decoration: BoxDecoration(
    color: Colors.white,
    borderRadius: BorderRadius.circular(19),
    border: Border.all(color: line),
  ),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              title,
              style: const TextStyle(fontSize: 11, color: muted),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
      const SizedBox(height: 13),
      FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Text(
          value,
          style: const TextStyle(
            fontSize: 21,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
      ),
      const SizedBox(height: 5),
      Text(
        caption,
        style: TextStyle(
          fontSize: 10,
          color: caption.startsWith('+') ? green : muted,
          fontWeight: FontWeight.w600,
        ),
      ),
    ],
  ),
);

Widget section(String title, String? action, VoidCallback? onTap) => Row(
  children: [
    Expanded(
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w800,
          color: ink,
        ),
      ),
    ),
    if (action != null)
      TextButton(
        onPressed: onTap,
        style: TextButton.styleFrom(
          foregroundColor: blue,
          padding: const EdgeInsets.symmetric(horizontal: 4),
        ),
        child: Text(
          action,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
        ),
      ),
  ],
);

Widget insight(
  IconData icon,
  Color color,
  Color background,
  String title,
  String body,
  String tag,
) => Container(
  padding: const EdgeInsets.all(15),
  decoration: BoxDecoration(
    color: Colors.white,
    borderRadius: BorderRadius.circular(19),
    border: Border.all(color: line),
  ),
  child: Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(13),
        ),
        child: Icon(icon, color: color, size: 21),
      ),
      const SizedBox(width: 12),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              tag,
              style: TextStyle(
                color: color,
                fontSize: 10,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              title,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w800,
                color: ink,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              body,
              style: const TextStyle(fontSize: 11, color: muted, height: 1.5),
            ),
          ],
        ),
      ),
    ],
  ),
);

Widget chart() {
  const values = [0.36, 0.55, 0.42, 0.78, 0.62, 0.91, 0.70];
  const days = ['월', '화', '수', '목', '금', '토', '일'];
  return Container(
    padding: const EdgeInsets.fromLTRB(17, 17, 17, 14),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('이번 주 매출 추이', style: TextStyle(color: muted, fontSize: 12)),
        const SizedBox(height: 5),
        const Text(
          '₩2,845,000',
          style: TextStyle(
            color: ink,
            fontSize: 23,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 18),
        SizedBox(
          height: 110,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: List.generate(
              values.length,
              (i) => Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 5),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Expanded(
                        child: Align(
                          alignment: Alignment.bottomCenter,
                          child: FractionallySizedBox(
                            heightFactor: values[i],
                            child: Container(
                              decoration: BoxDecoration(
                                color: i == 5 ? blue : const Color(0xFFD9E8FF),
                                borderRadius: BorderRadius.circular(7),
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        days[i],
                        style: TextStyle(
                          fontSize: 10,
                          color: i == 5 ? blue : muted,
                          fontWeight: i == 5
                              ? FontWeight.w800
                              : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    ),
  );
}
