
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User
from store.models import Store
import uuid


# ?뚯썝媛??寃利?諛??ъ슜???앹꽦
class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        # 以묐났 ?꾩씠???먮룞 寃利?
        fields = ['username', 'email', 'password', 'nickname', 'phone']
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

    def to_internal_value(self, data):
        # The Flutter form labels the account field "email", while the user
        # model authenticates with username. Accept both request contracts.
        if isinstance(data, dict) and "username" not in data and "email" in data:
            data = {**data, "username": data["email"]}
        return super().to_internal_value(data)
    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                '?대? 媛?낅맂 ?대찓?쇱엯?덈떎.'
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
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            username=username,
            email=validated_data['email'],
            password=validated_data['password'],
            nickname=validated_data.get('nickname', ''),
            phone=validated_data.get('phone', '')
        )

        return user


# ?ъ슜??怨듦컻 ?뺣낫 ?묐떟
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'phone']
        read_only_fields = fields


# ?대찓??濡쒓렇???낅젰 寃利?
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False
    )

    def to_internal_value(self, data):
        # Keep older clients sending username working, and accept the current
        # Flutter client's email field as an alias for username.
        if isinstance(data, dict) and "username" not in data and "email" in data:
            data = {**data, "username": data["email"]}
        return super().to_internal_value(data)

    def validate(self, attrs):
        # 鍮꾨?踰덊샇 ?뺤씤 諛?鍮꾪솢??怨꾩젙 李⑤떒
        identifier = attrs['username']
        user = User.objects.filter(username=identifier).first()
        if user is None:
            user = User.objects.filter(email__iexact=identifier).first()
        if user is not None:
            attrs['username'] = user.get_username()
        user = authenticate(request=self.context.get('request'), **attrs)
        # ?몄쬆 ?ㅽ뙣 硫붿떆吏 ?듭씪
        email = attrs['email'].strip().lower()

        user_record = User.objects.filter(
            email__iexact=email
        ).order_by('id').first()

        if user_record is None:
            raise serializers.ValidationError(
                '?대찓???먮뒗 鍮꾨?踰덊샇媛 ?щ컮瑜댁? ?딆뒿?덈떎.'
            )

        user = authenticate(
            request=self.context.get('request'),
            username=user_record.username,
            password=attrs['password']
        )

        if user is None:
            raise serializers.ValidationError(
                '?대찓???먮뒗 鍮꾨?踰덊샇媛 ?щ컮瑜댁? ?딆뒿?덈떎.'
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
