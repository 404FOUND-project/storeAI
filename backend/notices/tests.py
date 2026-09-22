from datetime import timedelta

from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from member.models import User
from .models import Notice


class NoticeTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='secret', is_staff=True)
        self.member = User.objects.create_user(username='member', password='secret')
        self.notice = Notice.objects.create(title='첫 공지', content='공지 내용', author=self.admin)
        self.list_url = reverse('notices:list')
        self.detail_url = reverse('notices:detail', args=[self.notice.pk])

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_public_list_and_detail(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], '첫 공지')
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['author'], self.admin.pk)
        self.assertNotIn('password', response.data)
        self.assertNotIn('phone', response.data)

    def test_pagination_and_newest_first(self):
        for index in range(21):
            Notice.objects.create(title=f'공지 {index}', content='내용', author=self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data['count'], 22)
        self.assertEqual(len(response.data['results']), 20)
        self.assertEqual(response.data['results'][0]['title'], '공지 20')
        self.assertIsNotNone(response.data['next'])
        response = self.client.get(self.list_url, {'page': 2})
        self.assertEqual(len(response.data['results']), 2)
        self.assertIsNone(response.data['next'])
        self.assertEqual(self.client.get(self.list_url, {'page': 99}).status_code, 404)

    def test_anonymous_cannot_write(self):
        self.assert_write_denied(401)

    def test_member_cannot_write(self):
        self.authenticate(self.member)
        self.assert_write_denied(403)

    def assert_write_denied(self, expected):
        payload = {'title': '변경', 'content': '변경 내용'}
        self.assertEqual(self.client.post(self.list_url, payload).status_code, expected)
        self.assertEqual(self.client.put(self.detail_url, payload).status_code, expected)
        self.assertEqual(self.client.patch(self.detail_url, payload).status_code, expected)
        self.assertEqual(self.client.delete(self.detail_url).status_code, expected)
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.title, '첫 공지')
        self.assertEqual(Notice.objects.count(), 1)

    def test_admin_create_ignores_forged_author(self):
        self.authenticate(self.admin)
        response = self.client.post(self.list_url, {
            'title': '새 공지', 'content': '새 내용', 'author': self.member.pk,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['author'], self.admin.pk)
        self.assertEqual(Notice.objects.get(pk=response.data['id']).author, self.admin)

    def test_admin_update_preserves_author_and_creation_time(self):
        other_admin = User.objects.create_user(username='other', is_staff=True)
        self.authenticate(other_admin)
        created_at = self.notice.created_at
        # 시스템 시계 해상도와 무관한 수정 시각 검증
        updated_at = self.notice.updated_at - timedelta(days=1)
        Notice.objects.filter(pk=self.notice.pk).update(updated_at=updated_at)
        response = self.client.patch(self.detail_url, {
            'title': '수정 공지', 'author': other_admin.pk,
            'created_at': '2000-01-01T00:00:00Z',
        })
        self.assertEqual(response.status_code, 200)
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.title, '수정 공지')
        self.assertEqual(self.notice.content, '공지 내용')
        self.assertEqual(self.notice.author, self.admin)
        self.assertEqual(self.notice.created_at, created_at)
        self.assertGreater(self.notice.updated_at, updated_at)
        response = self.client.put(self.detail_url, {'title': '전체 수정', 'content': '새 내용'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['content'], '새 내용')

    def test_admin_delete(self):
        self.authenticate(self.admin)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        self.assertFalse(Notice.objects.exists())
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)

    def test_invalid_input(self):
        self.authenticate(self.admin)
        for payload in ({}, {'title': '제목'}, {'content': '내용'},
                        {'title': ' ', 'content': '내용'},
                        {'title': '제목', 'content': ' '},
                        {'title': '가' * 201, 'content': '내용'}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(self.list_url, payload).status_code, 400)
        self.assertEqual(self.client.put(self.detail_url, {'title': '제목'}).status_code, 400)
        self.assertEqual(self.client.patch(self.detail_url, {'title': ''}).status_code, 400)
        self.assertEqual(Notice.objects.count(), 1)

    def test_missing_notice(self):
        self.authenticate(self.admin)
        url = reverse('notices:detail', args=[9999])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {'title': '제목'}).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_deleted_author_preserves_notice(self):
        self.admin.delete()
        self.notice.refresh_from_db()
        self.assertIsNone(self.notice.author)
        self.assertIsNone(self.client.get(self.detail_url).data['author'])

    def test_invalid_token_rejected_even_for_read(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid')
        self.assertEqual(self.client.get(self.list_url).status_code, 401)
        self.assertEqual(self.client.get(self.detail_url).status_code, 401)

    def test_inactive_admin_cannot_write(self):
        self.authenticate(self.admin)
        self.admin.is_active = False
        self.admin.save()
        self.assert_write_denied(401)
