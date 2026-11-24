import 'package:flutter/material.dart';

import '../../core/network/auth_service.dart';

class LoginScreen extends StatefulWidget {
  final Future<void> Function(Map<String, dynamic> result) onLoginSuccess;

  const LoginScreen({super.key, required this.onLoginSuccess});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final AuthService _authService = AuthService();
  final _formKey = GlobalKey<FormState>();

  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _passwordConfirmController = TextEditingController();
  final _nicknameController = TextEditingController();
  final _phoneController = TextEditingController();

  bool _isSignup = false;
  bool _isLoading = false;
  bool _hidePassword = true;

  static const Color blue = Color(0xFF3182F6);
  static const Color ink = Color(0xFF1B2B45);
  static const Color muted = Color(0xFF697386);
  static const Color bg = Color(0xFFF4F7FB);

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _passwordConfirmController.dispose();
    _nicknameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      if (_isSignup) {
        await _authService.signup(
          email: _emailController.text.trim(),
          password: _passwordController.text,
          nickname: _nicknameController.text.trim(),
          phone: _phoneController.text.trim(),
        );

        if (!mounted) return;

        _passwordController.clear();
        _passwordConfirmController.clear();

        setState(() => _isSignup = false);

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('회원가입이 완료됐어요. 로그인해 주세요.'),
            backgroundColor: Color(0xFF15956F),
          ),
        );
      } else {
        final result = await _authService.login(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );

        await widget.onLoginSuccess(result);
      }
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e.toString().replaceFirst('Exception: ', '')),
          backgroundColor: Colors.redAccent,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  InputDecoration _inputDecoration(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      prefixIcon: Icon(icon, color: muted, size: 20),
      filled: true,
      fillColor: bg,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFE8EBF0)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: blue, width: 1.5),
      ),
    );
  }

  Widget _textField({
    required String label,
    required IconData icon,
    required TextEditingController controller,
    String? Function(String?)? validator,
    TextInputType? keyboardType,
  }) {
    return TextFormField(
      controller: controller,
      decoration: _inputDecoration(label, icon),
      validator: validator,
      keyboardType: keyboardType,
    );
  }

  Widget _passwordField({
    required String label,
    required TextEditingController controller,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: _hidePassword,
      decoration: _inputDecoration(label, Icons.lock_outline_rounded).copyWith(
        suffixIcon: IconButton(
          icon: Icon(
            _hidePassword
                ? Icons.visibility_off_outlined
                : Icons.visibility_outlined,
            color: muted,
          ),
          onPressed: () {
            setState(() => _hidePassword = !_hidePassword);
          },
        ),
      ),
      validator: validator,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 30),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 25),

                  // 로고
                  const Icon(Icons.coffee_rounded, color: blue, size: 55),
                  const SizedBox(height: 15),

                  const Text(
                    '카페온',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 29,
                      fontWeight: FontWeight.w900,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 8),

                  Text(
                    _isSignup ? '카페온과 함께 스마트한 매장 운영을 시작해 보세요.' : 'AI 카페 운영 매니저',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 13, color: muted),
                  ),

                  const SizedBox(height: 40),

                  Text(
                    _isSignup ? '회원가입' : '로그인',
                    style: const TextStyle(
                      fontSize: 23,
                      fontWeight: FontWeight.w800,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 8),

                  Text(
                    _isSignup ? '회원 정보를 입력해 주세요.' : '계정에 로그인하고 매장 관리를 시작하세요.',
                    style: const TextStyle(fontSize: 12, color: muted),
                  ),

                  const SizedBox(height: 25),

                  // 이메일
                  _textField(
                    label: '이메일',
                    icon: Icons.email_outlined,
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return '아이디를 입력해 주세요.';
                      }
                      return null;
                    },
                  ),

                  const SizedBox(height: 14),

                  // 비밀번호
                  _passwordField(
                    label: '비밀번호',
                    controller: _passwordController,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return '비밀번호를 입력해 주세요.';
                      }
                      if (_isSignup && value.length < 8) {
                        return '비밀번호는 8자 이상 입력해 주세요.';
                      }
                      return null;
                    },
                  ),

                  // 회원가입 전용 입력
                  if (_isSignup) ...[
                    const SizedBox(height: 14),

                    _passwordField(
                      label: '비밀번호 확인',
                      controller: _passwordConfirmController,
                      validator: (value) {
                        if (value != _passwordController.text) {
                          return '비밀번호가 일치하지 않습니다.';
                        }
                        return null;
                      },
                    ),

                    const SizedBox(height: 14),

                    _textField(
                      label: '닉네임 (선택)',
                      icon: Icons.badge_outlined,
                      controller: _nicknameController,
                    ),

                    const SizedBox(height: 14),

                    _textField(
                      label: '전화번호 (선택)',
                      icon: Icons.phone_outlined,
                      controller: _phoneController,
                      keyboardType: TextInputType.phone,
                    ),
                  ],

                  const SizedBox(height: 25),

                  // 로그인 / 회원가입 버튼
                  SizedBox(
                    height: 54,
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _submit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: blue,
                        foregroundColor: Colors.white,
                        disabledBackgroundColor: blue.withValues(alpha: 0.5),
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      child: _isLoading
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2,
                              ),
                            )
                          : Text(
                              _isSignup ? '회원가입하기' : '로그인',
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                    ),
                  ),

                  const SizedBox(height: 20),

                  // 화면 전환
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        _isSignup ? '이미 계정이 있으신가요?' : '아직 회원이 아니신가요?',
                        style: const TextStyle(fontSize: 12, color: muted),
                      ),
                      TextButton(
                        onPressed: _isLoading
                            ? null
                            : () {
                                setState(() {
                                  _isSignup = !_isSignup;
                                  _formKey.currentState?.reset();
                                  _passwordConfirmController.clear();
                                });
                              },
                        child: Text(
                          _isSignup ? '로그인' : '회원가입',
                          style: const TextStyle(
                            color: blue,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
