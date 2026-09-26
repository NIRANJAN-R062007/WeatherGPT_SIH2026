import 'package:flutter/material.dart';

import 'chat_page.dart';
import 'warnings_page.dart';

void main() {
  runApp(const WeatherGptApp());
}

class WeatherGptApp extends StatelessWidget {
  const WeatherGptApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'WeatherGPT',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1565C0)),
        useMaterial3: true,
      ),
      home: const HomeShell(),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _pages = [ChatPage(), WarningsPage()];
  static const _titles = ['Ask WeatherGPT', 'Warnings'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_titles[_index])),
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: 'Ask'),
          NavigationDestination(icon: Icon(Icons.warning_amber_outlined), label: 'Warnings'),
        ],
      ),
    );
  }
}
