# ✅ Resume機能エラー修正完了

## 修正した問題
`'str' object has no attribute 'get'` エラーの原因と修正

## 修正内容

### 1. メソッド名の修正
- ❌ `list_resumable_projects()` → ✅ `get_resumable_projects()`
- ❌ `select_project()` → ✅ `show_project_menu()`
- ❌ `select_resume_point()` → ✅ `show_step_selection_menu()`

### 2. ロジックの修正
旧コード:
```python
projects = self.resume_manager.list_resumable_projects(self.work_dir)
if not project_dir:
    project_dir = self.resume_manager.select_project(projects)
status = self.resume_manager.load_status(project_dir)
```

新コード:
```python
if not project_dir:
    selected = self.resume_manager.show_project_menu()
    if not selected:
        return {'status': 'error', 'message': 'No project selected'}
    project_dir, status = selected
else:
    status = self.resume_manager.load_status(project_dir)
```

### 3. 再開ポイント選択の修正
```python
if restart_from:
    resume_from = ProcessStep(restart_from)
else:
    resume_from = self.resume_manager.show_step_selection_menu(status)
```

## テスト済み

✅ すべてのメソッドが正しく存在することを確認
✅ 古いメソッドが削除されていることを確認
✅ 修正されたコードが正しく適用されていることを確認

## 実行方法

```powershell
# venv環境で実行
python.exe .\video_transcript_analyzer.py --resume
```

これで以下のように動作します:
1. 利用可能なプロジェクトのメニューが表示される
2. プロジェクトを選択
3. 再開ポイントを選択（続きから/やり直し）
4. Geminiで処理を継続

## 確認事項
- Gemini APIキーが設定されていること
- config.yamlでGeminiが有効になっていること
- モデル名が `gemini-1.5-pro` になっていること

---
*修正完了: 2025-09-23*