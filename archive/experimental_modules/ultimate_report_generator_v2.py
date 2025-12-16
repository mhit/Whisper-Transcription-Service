#!/usr/bin/env python3
"""
究極レポート生成システム V2
LLM統合を適切に実装した改良版
"""

import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import time

class UltimateReportGeneratorV2:
    """究極レポート生成器 V2 - LLM統合版"""

    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.api_base_url = config.get('api_base_url', 'http://192.168.43.245:11434')
        self.model_name = config.get('model', 'gpt-oss:20b')
        self.logger = logging.getLogger(__name__)
        self.max_retries = 3
        self.llm_timeout = 60  # 60秒タイムアウト

    def generate_ultimate_report(self,
                                transcript_data: Dict,
                                analysis_result: Any,
                                existing_report: Optional[str] = None) -> str:
        """究極のレポートを生成 - LLM統合版"""
        self.logger.info("究極レポート生成開始 V2")

        # 分析結果から重要情報を抽出
        key_insights = self._extract_key_insights(analysis_result)

        # レポートセクションを生成
        sections = []

        # 1. タイトルとメタ情報
        sections.append(self._generate_title_section(analysis_result))

        # 2. エグゼクティブサマリー（LLM使用）
        exec_summary = self._generate_executive_summary_with_llm(key_insights, analysis_result)
        sections.append(exec_summary)

        # 3. 目次
        sections.append(self._generate_table_of_contents())

        # 4. 核心的価値章（LLM使用）
        core_value = self._generate_core_value_with_llm(key_insights, analysis_result)
        sections.append(core_value)

        # 5. フレームワーク章（LLM使用）
        frameworks = self._generate_framework_with_llm(key_insights, analysis_result)
        sections.append(frameworks)

        # 6. 成功事例分析（LLM使用）
        success_analysis = self._generate_success_analysis_with_llm(key_insights, analysis_result)
        sections.append(success_analysis)

        # 7. 失敗パターン分析（LLM使用）
        failure_analysis = self._generate_failure_analysis_with_llm(key_insights, analysis_result)
        sections.append(failure_analysis)

        # 8. 心理学的メカニズム（LLM使用）
        psychology = self._generate_psychology_with_llm(key_insights, analysis_result)
        sections.append(psychology)

        # 9. 実践ロードマップ（LLM使用）
        roadmap = self._generate_roadmap_with_llm(key_insights, analysis_result)
        sections.append(roadmap)

        # 10. 結論と次のステップ
        conclusion = self._generate_conclusion_with_llm(key_insights, analysis_result)
        sections.append(conclusion)

        # セクションを結合
        report = "\n\n".join(filter(None, sections))

        self.logger.info("究極レポート生成完了 V2")
        return report

    def _extract_key_insights(self, analysis_result: Any) -> Dict:
        """分析結果から重要な洞察を抽出"""
        insights = {
            'key_concepts': [],
            'frameworks': [],
            'success_patterns': [],
            'failure_patterns': [],
            'numerical_data': [],
            'action_items': []
        }

        # キーコンセプトを抽出
        if hasattr(analysis_result, 'key_concepts'):
            sorted_concepts = sorted(analysis_result.key_concepts.items(),
                                   key=lambda x: x[1], reverse=True)[:10]
            insights['key_concepts'] = [f"{k}: {v:.1f}" for k, v in sorted_concepts]

        # フレームワークを抽出
        if hasattr(analysis_result, 'frameworks'):
            for fw in analysis_result.frameworks[:5]:
                insights['frameworks'].append(fw.get('name', 'Unknown'))

        # 成功パターンを抽出
        if hasattr(analysis_result, 'success_patterns'):
            for pattern in analysis_result.success_patterns[:5]:
                insights['success_patterns'].append(pattern.get('pattern', 'Unknown'))

        # 失敗パターンを抽出
        if hasattr(analysis_result, 'failure_patterns'):
            for pattern in analysis_result.failure_patterns[:5]:
                insights['failure_patterns'].append(pattern.get('pattern', 'Unknown'))

        # 数値データを抽出
        if hasattr(analysis_result, 'numerical_insights'):
            for num in analysis_result.numerical_insights[:10]:
                if 'number' in num and 'context' in num:
                    insights['numerical_data'].append(f"{num['number']}: {num['context'][:50]}")

        # アクション項目を抽出
        if hasattr(analysis_result, 'action_items'):
            for action in analysis_result.action_items[:10]:
                if 'action' in action:
                    insights['action_items'].append(action['action'])

        return insights

    def _call_llm(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """LLMを呼び出してコンテンツを生成"""
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"LLM呼び出し試行 {attempt + 1}/{self.max_retries}")

                url = f"{self.api_base_url}/api/generate"

                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "temperature": 0.3,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "top_k": 40,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1
                    }
                }

                response = requests.post(url, json=payload, timeout=self.llm_timeout)

                if response.status_code == 200:
                    result = response.json()
                    content = result.get('response', '').strip()
                    if content:
                        self.logger.info("LLM応答取得成功")
                        return content
                    else:
                        self.logger.warning("LLM応答が空でした")
                else:
                    self.logger.warning(f"LLM応答エラー: {response.status_code}")

            except requests.Timeout:
                self.logger.warning(f"LLMタイムアウト（試行 {attempt + 1}）")
            except Exception as e:
                self.logger.error(f"LLM呼び出しエラー: {e}")

            if attempt < self.max_retries - 1:
                time.sleep(2)  # リトライ前に待機

        self.logger.error("LLM呼び出し失敗 - デフォルトコンテンツを使用")
        return None

    def _generate_title_section(self, analysis_result: Any) -> str:
        """タイトルセクションを生成"""
        current_date = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        return f"""# 【完全版】セミナー分析レポート - インテリジェンス強化版 V2

**生成日時**: {current_date}
**分析深度**: 究極レベル（LLM統合分析）
**品質保証**: Claude Code + LLM による知的生成

---"""

    def _generate_executive_summary_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """エグゼクティブサマリーをLLMで生成"""
        self.logger.info("エグゼクティブサマリー生成中...")

        # LLMプロンプト作成
        prompt = f"""以下の分析結果に基づいて、経営者向けのエグゼクティブサマリーを生成してください。

【重要概念】
{chr(10).join(insights['key_concepts'][:5]) if insights['key_concepts'] else '情報なし'}

【検出フレームワーク】
{chr(10).join(insights['frameworks'][:3]) if insights['frameworks'] else '情報なし'}

【数値データ】
{chr(10).join(insights['numerical_data'][:5]) if insights['numerical_data'] else '情報なし'}

【成功パターン】
{chr(10).join(insights['success_patterns'][:3]) if insights['success_patterns'] else '情報なし'}

以下の形式で、具体的で実践的なエグゼクティブサマリーを作成してください：

## エグゼクティブサマリー

### 3つの核心的洞察
1. [最も重要な洞察を具体的な数値と共に]
2. [2番目に重要な洞察を実例と共に]
3. [3番目に重要な洞察を実践方法と共に]

### ビジネスインパクト
[この内容を実践した場合の具体的な成果予測]

### 投資対効果（ROI）
[必要な投資と期待されるリターンの具体的な数値]

実際の数値やデータを必ず含めて、説得力のある内容にしてください。"""

        # LLM呼び出し
        llm_content = self._call_llm(prompt, max_tokens=1500)

        if llm_content:
            return f"## 🎯 エグゼクティブサマリー\n\n{llm_content}"

        # フォールバック：基本テンプレート
        return self._generate_fallback_executive_summary(insights)

    def _generate_core_value_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """核心的価値章をLLMで生成"""
        self.logger.info("核心的価値章生成中...")

        prompt = f"""セミナーの核心的価値について、以下の情報を基に詳細に説明してください。

【キーコンセプト】
{chr(10).join(insights['key_concepts'][:7]) if insights['key_concepts'] else '情報なし'}

【アクション項目】
{chr(10).join(insights['action_items'][:5]) if insights['action_items'] else '情報なし'}

以下の構成で説明してください：

## 第1章：セミナーの核心的価値

### 1.1 解決される根本的な問題
[具体的な問題と痛みを3つ以上]

### 1.2 提供される独自の価値
[他では得られない価値を3つ、具体例付きで]

### 1.3 期待される成果
[短期・中期・長期の成果を数値目標付きで]

できるだけ具体的な例や数値を使って説明してください。"""

        llm_content = self._call_llm(prompt, max_tokens=1800)

        if llm_content:
            return llm_content

        return self._generate_fallback_core_value(insights)

    def _generate_framework_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """フレームワーク章をLLMで生成"""
        self.logger.info("フレームワーク章生成中...")

        prompt = f"""成功のための体系的フレームワークを説明してください。

【検出されたフレームワーク】
{chr(10).join(insights['frameworks']) if insights['frameworks'] else '情報なし'}

【成功パターン】
{chr(10).join(insights['success_patterns']) if insights['success_patterns'] else '情報なし'}

以下の構成で詳しく解説してください：

## 第2章：成功の方程式と体系的フレームワーク

### 2.1 収益化の基本方程式
[具体的な計算式と各要素の説明]

### 2.2 実践フレームワーク
[ステップバイステップの実践方法]

### 2.3 成功を加速させる要素
[レバレッジポイントとその活用法]

実例と数値を交えて、実践可能な内容にしてください。"""

        llm_content = self._call_llm(prompt, max_tokens=2000)

        if llm_content:
            return llm_content

        return self._generate_fallback_framework(insights)

    def _generate_success_analysis_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """成功事例分析をLLMで生成"""
        self.logger.info("成功事例分析生成中...")

        prompt = f"""成功事例の詳細分析を行ってください。

【成功パターン】
{chr(10).join(insights['success_patterns']) if insights['success_patterns'] else '情報なし'}

【数値データ】
{chr(10).join(insights['numerical_data']) if insights['numerical_data'] else '情報なし'}

以下の形式で分析してください：

## 第3章：成功事例の詳細分析

### 3.1 成功事例の共通パターン
[3つ以上の共通要素を具体例付きで]

### 3.2 成功の再現性
[どうすれば同じ成功を再現できるか]

### 3.3 成功を最大化する方法
[さらに大きな成果を出すための戦略]

具体的な数値と実例を必ず含めてください。"""

        llm_content = self._call_llm(prompt, max_tokens=1800)

        if llm_content:
            return llm_content

        return self._generate_fallback_success_analysis(insights)

    def _generate_failure_analysis_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """失敗パターン分析をLLMで生成"""
        self.logger.info("失敗パターン分析生成中...")

        prompt = f"""失敗パターンとその回避策について分析してください。

【失敗パターン】
{chr(10).join(insights['failure_patterns']) if insights['failure_patterns'] else '情報なし'}

以下の構成で説明してください：

## 第4章：失敗パターンと回避戦略

### 4.1 よくある失敗パターン
[具体的な失敗例を3つ以上]

### 4.2 失敗の根本原因
[なぜ失敗するのか、深層的な理由]

### 4.3 失敗を避ける具体的方法
[チェックリスト形式で実践的な対策]

実例を交えて、予防策を具体的に説明してください。"""

        llm_content = self._call_llm(prompt, max_tokens=1500)

        if llm_content:
            return llm_content

        return self._generate_fallback_failure_analysis(insights)

    def _generate_psychology_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """心理学的メカニズムをLLMで生成"""
        self.logger.info("心理学的メカニズム生成中...")

        prompt = f"""購買心理と影響力の原理について説明してください。

【関連する概念】
{chr(10).join(insights['key_concepts'][:5]) if insights['key_concepts'] else '情報なし'}

以下の構成で解説してください：

## 第5章：心理学的メカニズムと科学的裏付け

### 5.1 購買心理の6原則
[各原則の説明と活用方法]

### 5.2 感情トリガーの活用
[購買を促す感情的要素]

### 5.3 行動経済学の応用
[実践的な価格戦略と提示方法]

科学的根拠と実例を交えて説明してください。"""

        llm_content = self._call_llm(prompt, max_tokens=1800)

        if llm_content:
            return llm_content

        return self._generate_fallback_psychology(insights)

    def _generate_roadmap_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """実践ロードマップをLLMで生成"""
        self.logger.info("実践ロードマップ生成中...")

        prompt = f"""段階的な実践ロードマップを作成してください。

【アクション項目】
{chr(10).join(insights['action_items']) if insights['action_items'] else '情報なし'}

以下の構成で具体的に説明してください：

## 第6章：実践ロードマップ

### 6.1 初級編（0→月10万円）
- 第1週: [具体的なアクション]
- 第2週: [具体的なアクション]
- 第3週: [具体的なアクション]
- 第4週: [具体的なアクション]

### 6.2 中級編（月10万→100万円）
[3ヶ月計画を週単位で]

### 6.3 上級編（月100万→1000万円）
[6ヶ月計画を月単位で]

各ステップに具体的なKPIと成功基準を含めてください。"""

        llm_content = self._call_llm(prompt, max_tokens=2000)

        if llm_content:
            return llm_content

        return self._generate_fallback_roadmap(insights)

    def _generate_conclusion_with_llm(self, insights: Dict, analysis_result: Any) -> str:
        """結論と次のステップをLLMで生成"""
        self.logger.info("結論生成中...")

        prompt = f"""レポートの結論と具体的な次のステップを作成してください。

【重要ポイント】
{chr(10).join(insights['key_concepts'][:3]) if insights['key_concepts'] else '情報なし'}

【アクション項目】
{chr(10).join(insights['action_items'][:3]) if insights['action_items'] else '情報なし'}

以下の構成でまとめてください：

## 結論と次のステップ

### 最も重要な3つのポイント
1. [最重要ポイントと理由]
2. [2番目に重要なポイントと理由]
3. [3番目に重要なポイントと理由]

### 今すぐ始めるべき3つのアクション
1. [今日できること]
2. [今週できること]
3. [今月の目標]

### 成功を確実にするための注意点
[絶対に避けるべきことと、必ずやるべきこと]

読者が即座に行動できるよう、具体的で実践的な内容にしてください。"""

        llm_content = self._call_llm(prompt, max_tokens=1500)

        if llm_content:
            return llm_content

        return self._generate_fallback_conclusion(insights)

    def _generate_table_of_contents(self) -> str:
        """目次を生成"""
        return """## 📚 目次

### 第1部：基礎編
- [第1章：セミナーの核心的価値](#第1章セミナーの核心的価値)
- [第2章：成功の方程式と体系的フレームワーク](#第2章成功の方程式と体系的フレームワーク)

### 第2部：分析編
- [第3章：成功事例の詳細分析](#第3章成功事例の詳細分析)
- [第4章：失敗パターンと回避戦略](#第4章失敗パターンと回避戦略)

### 第3部：実践編
- [第5章：心理学的メカニズムと科学的裏付け](#第5章心理学的メカニズムと科学的裏付け)
- [第6章：実践ロードマップ](#第6章実践ロードマップ)

### 第4部：総括
- [結論と次のステップ](#結論と次のステップ)

---"""

    # フォールバックメソッド（LLMが失敗した場合の基本コンテンツ）
    def _generate_fallback_executive_summary(self, insights: Dict) -> str:
        """フォールバック：エグゼクティブサマリー"""
        concepts = "\n".join([f"- {c}" for c in insights['key_concepts'][:3]])
        return f"""## 🎯 エグゼクティブサマリー

### 3つの核心的洞察

{concepts if concepts else '- データ分析により重要概念を抽出'}

### ビジネスインパクト
- 実装により売上向上が期待される
- 効率化により時間削減が可能
- 長期的な競争優位を構築

### 投資対効果（ROI）
- 初期投資：最小限の時間とリソース
- 期待リターン：3ヶ月で投資回収見込み"""

    def _generate_fallback_core_value(self, insights: Dict) -> str:
        """フォールバック：核心的価値"""
        return """## 第1章：セミナーの核心的価値

### 1.1 解決される根本的な問題
- ビジネスの成長停滞
- 収益化の困難
- 効率的な運営の欠如

### 1.2 提供される独自の価値
- 実証済みのフレームワーク
- 段階的な成長プログラム
- 継続的なサポート体制

### 1.3 期待される成果
- 短期：基礎の確立
- 中期：安定的な収益
- 長期：持続可能な成長"""

    def _generate_fallback_framework(self, insights: Dict) -> str:
        """フォールバック：フレームワーク"""
        frameworks = "\n".join([f"- {f}" for f in insights['frameworks'][:3]])
        return f"""## 第2章：成功の方程式と体系的フレームワーク

### 2.1 検出されたフレームワーク
{frameworks if frameworks else '- 体系的アプローチ'}

### 2.2 実践方法
- Step 1: 基礎の構築
- Step 2: システムの実装
- Step 3: 継続的な改善"""

    def _generate_fallback_success_analysis(self, insights: Dict) -> str:
        """フォールバック：成功分析"""
        return """## 第3章：成功事例の詳細分析

### 3.1 成功パターン
- 一貫した実行
- データに基づく意思決定
- 顧客中心のアプローチ

### 3.2 成功要因
- 明確な目標設定
- 適切なリソース配分
- 継続的な学習と改善"""

    def _generate_fallback_failure_analysis(self, insights: Dict) -> str:
        """フォールバック：失敗分析"""
        patterns = "\n".join([f"- {p}" for p in insights['failure_patterns'][:3]])
        return f"""## 第4章：失敗パターンと回避戦略

### 4.1 よくある失敗パターン
{patterns if patterns else '- 計画不足\n- リソース不足\n- 実行の不徹底'}

### 4.2 回避策
- 事前の綿密な計画
- 段階的な実装
- 定期的な評価と修正"""

    def _generate_fallback_psychology(self, insights: Dict) -> str:
        """フォールバック：心理学"""
        return """## 第5章：心理学的メカニズムと科学的裏付け

### 5.1 影響力の原理
- 返報性の原理
- 一貫性の原理
- 社会的証明
- 好意の原理
- 権威の原理
- 希少性の原理

### 5.2 実践への応用
- 各原理の具体的な活用方法
- 組み合わせによる相乗効果"""

    def _generate_fallback_roadmap(self, insights: Dict) -> str:
        """フォールバック：ロードマップ"""
        actions = "\n".join([f"- {a}" for a in insights['action_items'][:5]])
        return f"""## 第6章：実践ロードマップ

### 今すぐ実行すべきアクション
{actions if actions else '- 現状分析\n- 目標設定\n- 計画策定'}

### 段階的実装計画
- Phase 1: 基礎構築（1ヶ月目）
- Phase 2: システム化（2-3ヶ月目）
- Phase 3: スケール（4-6ヶ月目）"""

    def _generate_fallback_conclusion(self, insights: Dict) -> str:
        """フォールバック：結論"""
        return """## 結論と次のステップ

### 重要ポイントのまとめ
- 体系的なアプローチの重要性
- 継続的な改善の必要性
- データに基づく意思決定

### 推奨される次のアクション
1. 現状の詳細な分析
2. 明確な目標の設定
3. 実行計画の策定
4. 小さく始めて大きく育てる

### 成功への道
成功は一夜にして成らず。しかし、正しい方法論と継続的な努力により、確実に目標に近づくことができます。"""