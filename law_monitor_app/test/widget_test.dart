import 'package:flutter_test/flutter_test.dart';
import 'package:law_monitor/main.dart';

void main() {
  testWidgets('App renders dashboard', (WidgetTester tester) async {
    await tester.pumpWidget(const LawMonitorApp());
    expect(find.text('法規異動監控'), findsOneWidget);
  });
}
