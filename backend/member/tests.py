from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import User


# 회원가입·인증 API 검증
# 테스트별 DB 변경 격리
class AuthenticationTests(APITestCase):
    def setUp(self):
        self.payload = {
            'username': 'storeowner',
            'password': 'River!Cedar72Moon',
            'nickname': '사장님',
            'phone': '010-1234-5678',
        }

    # 테스트별 사용자 조건 설정
    def create_user(self, **overrides):
        return User.objects.create_user(**{**self.payload, **overrides})

    def login(self, **overrides):
        data = {key: self.payload[key] for key in ('username', 'password')}
        return self.client.post(reverse('login'), {**data, **overrides})

    def test_signup_hashes_password_and_does_not_expose_it(self):
        response = self.client.post(reverse('signup'), self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        user = User.objects.get(username=self.payload['username'])
        self.assertTrue(user.check_password(self.payload['password']))
        self.assertNotEqual(user.password, self.payload['password'])
        self.assertEqual(user.nickname, self.payload['nickname'])
        self.assertEqual(user.phone, self.payload['phone'])

    def test_signup_accepts_only_required_fields(self):
        response = self.client.post(reverse('signup'), {
            key: self.payload[key] for key in ('username', 'password')
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_signup_rejects_duplicate_username(self):
        self.create_user()
        response = self.client.post(reverse('signup'), self.payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_signup_rejects_weak_passwords(self):
        for password in ('short', '123456789123', 'password', 'storeowner'):
            with self.subTest(password=password):
                response = self.client.post(reverse('signup'), {
                    **self.payload, 'password': password,
                })
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('password', response.data)
        self.assertFalse(User.objects.exists())

    def test_missing_fields_are_rejected(self):
        for endpoint in ('signup', 'login'):
            for data in ({}, {'username': 'owner'}, {'password': 'secret'}):
                with self.subTest(endpoint=endpoint, data=data):
                    response = self.client.post(reverse(endpoint), data)
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_cannot_grant_privileges(self):
        self.client.post(reverse('signup'), {
            **self.payload, 'is_staff': True, 'is_superuser': True,
        })
        user = User.objects.get()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_login_me_logout_flow(self):
        user = self.create_user()
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['token']
        self.assertEqual(response.data['user']['id'], user.pk)
        self.assertNotIn('password', response.data['user'])
        # 인증 토큰 헤더 설정
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get(reverse('me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], user.username)
        self.assertNotIn('password', response.data)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 204)
        self.assertFalse(Token.objects.filter(key=token).exists())
        # 로그아웃 후 토큰 무효화 확인
        self.assertEqual(self.client.get(reverse('me')).status_code, 401)
        self.client.credentials()
        self.assertNotEqual(self.login().data['token'], token)

    def test_repeated_login_reuses_active_token(self):
        self.create_user()
        self.assertEqual(self.login().data['token'], self.login().data['token'])

    def test_login_failure_does_not_disclose_account_existence(self):
        self.create_user()
        wrong_password = self.login(password='incorrect')
        missing_user = self.login(username='missing')
        self.assertEqual(wrong_password.status_code, 400)
        self.assertEqual(missing_user.status_code, 400)
        self.assertEqual(wrong_password.data, missing_user.data)
        self.assertFalse(Token.objects.exists())

    def test_inactive_user_cannot_login_or_use_token(self):
        user = self.create_user(is_active=False)
        self.assertEqual(self.login().status_code, 400)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.assertEqual(self.client.get(reverse('me')).status_code, 401)

    def test_protected_endpoints_require_valid_token(self):
        for authorization in ('', 'Token invalid'):
            self.client.credentials(HTTP_AUTHORIZATION=authorization)
            self.assertEqual(self.client.get(reverse('me')).status_code, 401)
            self.assertEqual(self.client.post(reverse('logout')).status_code, 401)

    def test_password_whitespace_is_preserved(self):
        password = '  River!Cedar72Moon  '
        response = self.client.post(reverse('signup'), {
            **self.payload, 'password': password,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.login(password=password).status_code, 200)
        self.assertEqual(self.login(password=password.strip()).status_code, 400)
