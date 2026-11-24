from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User
from store.models import Store


# 회원가입 검증 및 사용자 생성
class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        # 중복 아이디 자동 검증
        fields = ['username', 'email', 'password', 'nickname', 'phone']
        extra_kwargs = {
            # 비밀번호 응답 제외 및 공백 보존
            'password': {'write_only': True, 'trim_whitespace': False}
        }

    def to_internal_value(self, data):
        # The Flutter form labels the account field "email", while the user
        # model authenticates with username. Accept both request contracts.
        if isinstance(data, dict) and "username" not in data and "email" in data:
            data = {**data, "username": data["email"]}
        return super().to_internal_value(data)

    def validate(self, attrs):
        # 유사성 검증용 사용자 정보
        user = User(username=attrs.get('username', ''), nickname=attrs.get('nickname', ''))
        try:
            # Django 비밀번호 규칙 적용
            validate_password(attrs['password'], user=user)
        except ValidationError as error:
            # 비밀번호 검증 오류 반환 (400)
            raise serializers.ValidationError({'password': error.messages})
        return attrs

    def create(self, validated_data):
        # 비밀번호 해시 저장
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            nickname=validated_data.get('nickname', ''),
            phone=validated_data.get('phone', '')
        )
        return user


# 사용자 공개 정보 응답
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'phone']
        read_only_fields = fields


# 로그인 입력 검증
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def to_internal_value(self, data):
        # Keep older clients sending username working, and accept the current
        # Flutter client's email field as an alias for username.
        if isinstance(data, dict) and "username" not in data and "email" in data:
            data = {**data, "username": data["email"]}
        return super().to_internal_value(data)

    def validate(self, attrs):
        # 비밀번호 확인 및 비활성 계정 차단
        identifier = attrs['username']
        user = User.objects.filter(username=identifier).first()
        if user is None:
            user = User.objects.filter(email__iexact=identifier).first()
        if user is not None:
            attrs['username'] = user.get_username()
        user = authenticate(request=self.context.get('request'), **attrs)
        # 인증 실패 메시지 통일
        if user is None:
            raise serializers.ValidationError('아이디 또는 비밀번호가 올바르지 않습니다.')
        attrs['user'] = user
        return attrs


class StoreSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, min_value=-90, max_value=90,
        required=False, allow_null=True,
    )
    longitude = serializers.DecimalField(
        max_digits=10, decimal_places=7, min_value=-180, max_value=180,
        required=False, allow_null=True,
    )

    class Meta:
        model = Store
        fields = ['id', 'owner', 'name', 'address', 'phone',
                  'business_number', 'latitude', 'longitude', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']


class AdminUserSerializer(serializers.ModelSerializer):
    stores = StoreSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'nickname', 'phone', 'is_active', 'date_joined', 'stores']
        read_only_fields = ['id', 'date_joined', 'stores']
