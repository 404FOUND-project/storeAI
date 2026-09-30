from rest_framework import generics, permissions, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from store.models import Store
from .models import User
from .serializers import LoginSerializer, SignupSerializer, UserSerializer
from .serializers import AdminUserSerializer, StoreSerializer

# 회원가입 처리 (201)
class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = SignupSerializer
    # 비인증 접근 허용
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


# 로그인 및 토큰 발급
class LoginView(APIView):
    # 비인증 접근 허용
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        # 입력·인증 오류 반환 (400)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        # 사용자별 단일 토큰 재사용 (자동 만료 없음)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': UserSerializer(user).data})


# 토큰 인증 기반 내 정보 조회
class MeView(generics.RetrieveAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        # 현재 인증 사용자 반환
        return self.request.user


# 로그아웃 처리
class LogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 인증 토큰 삭제
        # 동일 토큰 사용 기기 인증 해제
        request.auth.delete()
        # 본문 없는 성공 응답 (204)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberPagination(PageNumberPagination):
    page_size = 20


class AdminMemberListView(generics.ListAPIView):
    queryset = User.objects.prefetch_related('stores').order_by('id')
    serializer_class = AdminUserSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]
    pagination_class = MemberPagination


class AdminMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.prefetch_related('stores')
    serializer_class = AdminUserSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]


class StoreRegistrationView(generics.CreateAPIView):
    serializer_class = StoreSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class AdminMemberStoreView(generics.RetrieveUpdateAPIView):
    serializer_class = StoreSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        member = get_object_or_404(User, pk=self.kwargs['member_pk'])
        return Store.objects.filter(owner=member)
