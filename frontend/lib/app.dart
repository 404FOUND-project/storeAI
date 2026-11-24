import 'package:flutter/material.dart';

import 'screens/auth_screen.dart';

const blue = Color(0xFF3182F6);
const ink = Color(0xFF1B2B45);
const muted = Color(0xFF697386);
const line = Color(0xFFE8EBF0);
const bg = Color(0xFFF4F7FB);
const green = Color(0xFF15956F);

class CafeOnApp extends StatelessWidget {
  const CafeOnApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: '카페온',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xFF1E232A),
      colorScheme: ColorScheme.fromSeed(seedColor: blue),
    ),
    home: const PhoneFrameScreen(),
  );
}

class PhoneFrameScreen extends StatelessWidget {
  const PhoneFrameScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF181C24),
      body: Center(
        child: Container(
          width: 390,
          height: 800,
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(40),
            border: Border.all(color: const Color(0xFF3A4252), width: 10),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.5),
                blurRadius: 30,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(30),
            child: Stack(
              children: [
                // 휴대폰 프레임 내부에서 화면을 전환하도록 중첩 Navigator 사용
                Navigator(
                  onGenerateRoute: (settings) => MaterialPageRoute<void>(
                    settings: settings,
                    builder: (_) => const AuthScreen(),
                  ),
                ),
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 30,
                  child: IgnorePointer(
                    child: Center(
                      child: Container(
                        width: 110,
                        height: 22,
                        decoration: const BoxDecoration(
                          color: Colors.black,
                          borderRadius: BorderRadius.vertical(
                            bottom: Radius.circular(14),
                          ),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              width: 10,
                              height: 10,
                              decoration: const BoxDecoration(
                                color: Color(0xFF111418),
                                shape: BoxShape.circle,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
