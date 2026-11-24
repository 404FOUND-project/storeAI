import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/main.dart';

void main() {
  testWidgets('StoreAI app launches without errors', (WidgetTester tester) async {
    await tester.pumpWidget(const CafeOnApp());

    expect(tester.takeException(), isNull);
  });
}