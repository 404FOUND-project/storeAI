import uuid

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User
from store.models import Store


class SignupSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        required=False,
        allow_blank=True
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'nickname',
            'phone'
        ]
        extra_kwargs = {
            'password': {
                'write_only': True,
                'trim_whitespace': False
            }
        }

    def validate_email(self, value):
        value = value.strip().lower()

        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                '이미 가입된 이메일입니다.'
            )

        return value

    def validate(self, attrs):
        username = attrs.get('username', '').strip()
        email = attrs.get('email', '').strip().lower()

        if not username and not email:
            raise serializers.ValidationError(
                '아이디 또는 이메일을 입력해 주세요.'
            )

        user = User(
            email=email,
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
        username = validated_data.get('username', '').strip()

        if not username:
            username = f"email_{uuid.uuid4().hex}"

        user = User.objects.create_user(
            username=username,
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            nickname=validated_data.get('nickname', ''),
            phone=validated_data.get('phone', '')
        )

        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'nickname',
            'phone'
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=False,
        allow_blank=True
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True
    )
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False
    )

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        username = attrs.get('username', '').strip()

        if not email and not username:
            raise serializers.ValidationError(
                '이메일 또는 아이디를 입력해 주세요.'
            )

        if email:
            user_record = User.objects.filter(
                email__iexact=email
            ).order_by('id').first()

            if user_record is None:
                raise serializers.ValidationError(
                    '이메일 또는 비밀번호가 올바르지 않습니다.'
                )

            username = user_record.username

        user = authenticate(
            request=self.context.get('request'),
            username=username,
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
        max_digits=10,
        decimal_places=7,
        min_value=-90,
        max_value=90,
        required=False,
        allow_null=True,
    )
    longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-180,
        max_value=180,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Store
        fields = [
            'id',
            'owner',
            'name',
            'address',
            'phone',
            'business_number',
            'latitude',
            'longitude',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'owner',
            'created_at'
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    stores = StoreSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'nickname',
            'phone',
            'is_active',
            'date_joined',
            'stores'
        ]
        read_only_fields = [
            'id',
            'date_joined',
            'stores'
        ]