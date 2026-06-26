// 法規異動監控 App — 入口

import 'package:flutter/material.dart';
import 'screens/dashboard.dart';
import 'screens/detail.dart';
import 'screens/diff_viewer.dart';
import 'screens/search.dart';
import 'screens/settings.dart';

void main() {
  runApp(const LawMonitorApp());
}

class LawMonitorApp extends StatelessWidget {
  const LawMonitorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '法規異動監控',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF1A5276),
        useMaterial3: true,
        brightness: Brightness.light,
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 2,
        ),
        cardTheme: CardTheme(
          elevation: 1,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      darkTheme: ThemeData(
        colorSchemeSeed: const Color(0xFF1A5276),
        useMaterial3: true,
        brightness: Brightness.dark,
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 2,
        ),
        cardTheme: CardTheme(
          elevation: 1,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      themeMode: ThemeMode.system,
      initialRoute: '/',
      onGenerateRoute: (settings) {
        switch (settings.name) {
          case '/':
            return MaterialPageRoute(builder: (_) => const Dashboard());
          case '/detail':
            final args = settings.arguments as Map<String, dynamic>;
            return MaterialPageRoute(
              builder: (_) => DetailScreen(
                pcode: args['pcode'] as String,
                name: args['name'] as String,
              ),
            );
          case '/diff':
            final args = settings.arguments as Map<String, dynamic>;
            return MaterialPageRoute(
              builder: (_) => DiffViewer(
                pcode: args['pcode'] as String,
                name: args['name'] as String,
              ),
            );
          case '/search':
            return MaterialPageRoute(builder: (_) => const SearchScreen());
          case '/settings':
            return MaterialPageRoute(builder: (_) => const SettingsScreen());
          default:
            return MaterialPageRoute(builder: (_) => const Dashboard());
        }
      },
    );
  }
}
