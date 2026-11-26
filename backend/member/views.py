
from rest_framework import generics, permissions, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from django.shortcuts import get_object_or_404

from store.models import Store
from .models import User
from .serializers import (
    LoginSerializer,
    SignupSerializer,
    UserSerializer,
    AdminUserSerializer,
    StoreSerializer,
)


# 회원가입 처리
class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


# 로그인 및 토큰 발급
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        # 사용자별 단일 토큰 재사용
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


# 내 정보 조회
class MeView(generics.RetrieveAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


# 로그아웃
class LogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# 관리자 회원 목록 페이지네이션
class MemberPagination(PageNumberPagination):
    page_size = 20


# 관리자 회원 목록 조회
class AdminMemberListView(generics.ListAPIView):
    queryset = User.objects.prefetch_related('stores').order_by('id')
    serializer_class = AdminUserSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]
    pagination_class = MemberPagination


# 관리자 회원 상세 조회 / 수정 / 삭제
class AdminMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.prefetch_related('stores')
    serializer_class = AdminUserSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]


# 매장 등록 및 목록 조회
class StoreRegistrationView(generics.ListCreateAPIView):
    serializer_class = StoreSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            stores = Store.objects.all()
        else:
            stores = Store.objects.filter(
                owner=self.request.user
            )

        return stores.order_by('id')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


# 관리자의 특정 회원 매장 조회 및 수정
class AdminMemberStoreView(generics.RetrieveUpdateAPIView):
    serializer_class = StoreSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        member = get_object_or_404(
            User,
            pk=self.kwargs['member_pk']
        )
        return Store.objects.filter(owner=member)
