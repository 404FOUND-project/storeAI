# Member management API

Authentication: `Authorization: Token <token>`.
Administrator endpoints require an active user with `is_staff=True`.

| Method | URL | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/member/signup/` | Public | Register with username, password, optional nickname and phone |
| POST | `/member/login/` | Public | Return token and user |
| POST | `/member/logout/` | Authenticated | Revoke token, return 204 |
| GET | `/member/me/` | Authenticated | Current user |
| POST | `/member/stores/` | Authenticated | Register a store owned by current user, return 201 |
| GET | `/member/admin/members/` | Administrator | List members with stores, 20 per page (`?page=2`) |
| GET, PUT, PATCH | `/member/admin/members/{id}/` | Administrator | Read or update member |
| DELETE | `/member/admin/members/{id}/` | Administrator | Delete member, return 204 |
| GET, PUT, PATCH | `/member/admin/members/{member_id}/stores/{store_id}/` | Administrator | Read or update that member's store |

Editable member fields: username, email, first_name, last_name, nickname, phone,
is_active. Password and administrator privileges are not editable through these
endpoints. Responses never contain password hashes.

Store fields: name (required), address, phone, business_number, latitude,
longitude. Coordinates may be null; latitude must be within -90 to 90 and
longitude within -180 to 180. Store ownership cannot be reassigned. Multiple
stores per member are supported by the existing model.

Member deletion cascades to owned stores and their related data and revokes
the member's authentication token. Setting is_active=false blocks login and
authenticated access. Logout revokes the user's shared token on all devices.

Errors: 400 invalid input, 401 missing/invalid token, 403 non-administrator,
404 missing member/store or store not belonging to the URL's member.

Run backend tests with:
`python manage.py test --settings=config.test_settings`
