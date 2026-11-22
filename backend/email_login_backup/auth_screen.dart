import 'package:flutter/material.dart';

import '../app.dart' show blue, bg, ink, line, muted;
import '../core/network/backend_api.dart';
import 'main_screen.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _passwordConfirmController = TextEditingController();
  bool _isLogin = true;
  bool _isSubmitting = false;
  bool _obscurePassword = true;
  bool _obscurePasswordConfirm = true;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _passwordConfirmController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSubmitting = true);

    try {
      if (_isLogin) {
        await BackendApi.instance.login(
          username: _emailController.text.trim(),
          password: _passwordController.text,
        );
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const MainScreen()),
        );
      } else {
        await BackendApi.instance.signup(
          username: _emailController.text.trim(),
          password: _passwordController.text,
          nickname: _nameController.text.trim(),
        );
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('회원가입이 완료되었습니다. 로그인해 주세요.')),
        );
        setState(() => _isLogin = true);
        _passwordController.clear();
        _passwordConfirmController.clear();
      }
    } on BackendException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  String? _required(String? value, String label) {
    if (value == null || value.trim().isEmpty) return '$label을(를) 입력해 주세요.';
    return null;
  }

  String? _validateEmail(String? value) {
    final required = _required(value, '이메일');
    if (required != null) return required;
    if (!value!.contains('@')) return '올바른 이메일 주소를 입력해 주세요.';
    return null;
  }

  String? _validatePassword(String? value) {
    final required = _required(value, '비밀번호');
    if (required != null) return required;
    if (value!.length < 8) return '비밀번호는 8자 이상이어야 합니다.';
    return null;
  }

  InputDecoration _inputDecoration({
    required String label,
    required IconData icon,
    Widget? suffixIcon,
  }) {
    return InputDecoration(
      labelText: label,
      prefixIcon: Icon(icon, size: 20),
      suffixIcon: suffixIcon,
      filled: true,
      fillColor: const Color(0xFFF8FAFD),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: blue, width: 1.5),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: bg,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 38, 24, 28),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 58,
                    height: 58,
                    decoration: BoxDecoration(
                      color: blue,
                      borderRadius: BorderRadius.circular(19),
                      boxShadow: [
                        BoxShadow(
                          color: blue.withValues(alpha: 0.25),
                          blurRadius: 16,
                          offset: const Offset(0, 7),
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.storefront_rounded,
                      color: Colors.white,
                      size: 30,
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                Center(
                  child: Text(
                    _isLogin ? '다시 만나서 반가워요' : '매장 운영을 시작해 보세요',
                    style: const TextStyle(
                      color: ink,
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Center(
                  child: Text(
                    _isLogin
                        ? 'AI 경영비서에 로그인하고 매장 현황을 확인하세요.'
                        : '간단한 회원가입으로 매장 데이터를 관리하세요.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: muted, fontSize: 12),
                  ),
                ),
                const SizedBox(height: 30),
                if (!_isLogin) ...[
                  TextFormField(
                    controller: _nameController,
                    textInputAction: TextInputAction.next,
                    decoration: _inputDecoration(
                      label: '이름 또는 매장명',
                      icon: Icons.person_outline_rounded,
                    ),
                    validator: (value) => _required(value, '이름 또는 매장명'),
                  ),
                  const SizedBox(height: 14),
                ],
                TextFormField(
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.next,
                  decoration: _inputDecoration(
                    label: '이메일',
                    icon: Icons.mail_outline_rounded,
                  ),
                  validator: _validateEmail,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _passwordController,
                  obscureText: _obscurePassword,
                  textInputAction: _isLogin
                      ? TextInputAction.done
                      : TextInputAction.next,
                  decoration: _inputDecoration(
                    label: '비밀번호',
                    icon: Icons.lock_outline_rounded,
                    suffixIcon: IconButton(
                      tooltip: '비밀번호 표시',
                      onPressed: () =>
                          setState(() => _obscurePassword = !_obscurePassword),
                      icon: Icon(
                        _obscurePassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                    ),
                  ),
                  validator: _validatePassword,
                  onFieldSubmitted: (_) => _submit(),
                ),
                if (!_isLogin) ...[
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _passwordConfirmController,
                    obscureText: _obscurePasswordConfirm,
                    textInputAction: TextInputAction.done,
                    decoration: _inputDecoration(
                      label: '비밀번호 확인',
                      icon: Icons.lock_reset_outlined,
                      suffixIcon: IconButton(
                        tooltip: '비밀번호 확인 표시',
                        onPressed: () => setState(
                          () => _obscurePasswordConfirm =
                              !_obscurePasswordConfirm,
                        ),
                        icon: Icon(
                          _obscurePasswordConfirm
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                      ),
                    ),
                    validator: (value) {
                      final required = _required(value, '비밀번호 확인');
                      if (required != null) return required;
                      if (value != _passwordController.text) {
                        return '비밀번호가 일치하지 않습니다.';
                      }
                      return null;
                    },
                  ),
                ],
                if (_isLogin)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () => ScaffoldMessenger.of(context)
                          .showSnackBar(
                            const SnackBar(content: Text('비밀번호 찾기는 준비 중입니다.')),
                          ),
                      child: const Text('비밀번호를 잊으셨나요?'),
                    ),
                  )
                else
                  const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: FilledButton(
                    onPressed: _isSubmitting ? null : _submit,
                    style: FilledButton.styleFrom(
                      backgroundColor: blue,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    child: _isSubmitting
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(
                            _isLogin ? '로그인' : '회원가입',
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      _isLogin ? '계정이 없으신가요?' : '이미 계정이 있으신가요?',
                      style: const TextStyle(color: muted, fontSize: 12),
                    ),
                    TextButton(
                      onPressed: () => setState(() {
                        _isLogin = !_isLogin;
                        _formKey.currentState?.reset();
                      }),
                      child: Text(
                        _isLogin ? '회원가입' : '로그인',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
