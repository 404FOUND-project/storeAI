from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SHOW COLUMNS FROM member_user")
    print("USER_COLUMNS:")
    for row in cursor.fetchall():
        print(row)

    cursor.execute("SELECT app, name FROM django_migrations WHERE app IN (%s, %s) ORDER BY app, name", ["member", "sales"])
    print("\nMIGRATIONS:")
    for row in cursor.fetchall():
        print(row)
