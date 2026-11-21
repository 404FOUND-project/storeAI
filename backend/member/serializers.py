
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User
from store.models import Store
import uuid


# 회원가입 검증 및 사용자 생성
class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()

    class Meta:
        model = User
        fields = ['email', 'password', 'nickname', 'phone']
        extra_kwargs = {
            'password': {
                'write_only': True,
                'trim_whitespace': False
            }
        }

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                '이미 가입된 이메일입니다.'
            )

        return value

    def validate(self, attrs):
        user = User(
            email=attrs.get('email', ''),
            nickname=attrs.get('nickname', '')
        )

        try:
            validate_password(attrs['password'], user=user)
        except ValidationError as error:
            raise serializers.ValidationError({
                'password': error.messages
            })

        return attrs

    def create(self, validated_data):
        username = f"email_{uuid.uuid4().hex}"

        user = User.objects.create_user(
            username=username,
            email=validated_data['email'],
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


# 이메일 로그인 입력 검증
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False
    )

    def validate(self, attrs):
        email = attrs['email'].strip().lower()

        user_record = User.objects.filter(
            email__iexact=email
        ).order_by('id').first()

        if user_record is None:
            raise serializers.ValidationError(
                '이메일 또는 비밀번호가 올바르지 않습니다.'
            )

        user = authenticate(
            request=self.context.get('request'),
            username=user_record.username,
            password=attrs['password']
        )

        if user is None:
            raise serializers.ValidationError(
                '이메일 또는 비밀번호가 올바르지 않습니다.'
            )

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
        fields = [
            'id', 'owner', 'name', 'address', 'phone',
            'business_number', 'latitude', 'longitude', 'created_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at']


class AdminUserSerializer(serializers.ModelSerializer):
    stores = StoreSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'nickname', 'phone', 'is_active', 'date_joined', 'stores'
        ]
        read_only_fields = ['id', 'date_joined', 'stores']
