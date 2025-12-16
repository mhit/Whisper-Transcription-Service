# 📝 Whisper Transcript to Professional Report Generator

## 🎯 Core Mission
Transform Whisper transcript files into high-quality markdown reports with intelligent summarization, key moment identification, and strategic screenshot placement - producing reports that match or exceed the quality of `instagram_seminar_summary.md`.

## 📊 System Architecture

### Input Processing
```yaml
input:
  type: Whisper JSON transcript
  format:
    - segments with timestamps
    - text content
    - speaker identification (if available)
  location: output/transcripts/*.json
```

### Output Generation
```yaml
output:
  type: Markdown report
  location: output/reports/[video_name]_report.md
  screenshots: output/reports/screenshots/[video_name]/
  quality_target: 100/100 (Gemini Ultimate quality)
```

## 🔍 Content Analysis Framework

### 1. Transcript Segmentation Analysis
When processing a transcript, identify and categorize:

```python
segment_types = {
    "opening": "Introduction, speaker credentials, agenda",
    "problem_statement": "Pain points, challenges, issues addressed",
    "solution_presentation": "Main content, methods, strategies",
    "case_studies": "Examples, success stories, testimonials",
    "data_points": "Statistics, numbers, metrics, results",
    "action_items": "Steps, recommendations, how-to guides",
    "closing": "Summary, CTA, contact information"
}
```

### 2. Key Moment Detection Algorithm
Identify screenshot-worthy moments based on:

```python
screenshot_triggers = {
    "speaker_introduction": weight=0.9,
    "shocking_statistic": weight=1.0,  # e.g., "10万フォロワーで月3万円"
    "visual_demonstration": weight=0.95,
    "graph_or_chart_mention": weight=1.0,
    "before_after_comparison": weight=0.95,
    "success_story_peak": weight=0.85,
    "key_formula_or_method": weight=1.0,
    "emotional_moment": weight=0.8,
    "final_summary": weight=0.9
}
```

### 3. Topic Clustering
Group related segments into coherent topics:

```python
topic_patterns = [
    "revenue_model",      # 収益化, マネタイズ, 売上
    "growth_strategy",    # 成長, フォロワー, リーチ
    "content_creation",   # コンテンツ, 投稿, リール
    "case_study",        # 事例, 成功例, 実績
    "technical_tutorial", # 方法, やり方, ステップ
    "mindset",           # 考え方, マインド, 哲学
    "tools_resources"    # ツール, リソース, 使い方
]
```

## 📋 Report Generation Template

### Standard Structure
```markdown
# [📱/🎯/💡] [Title] 完全レポート

## 🎯 エグゼクティブサマリー
**「[Core Message in Bold]」**
[2-3 sentence overview capturing the essence]

### 📌 最重要ポイント
> **[Key Insight]** - [Supporting detail with specific example]

---

## 👥 講師プロフィール
![Opening scene](screenshots/opening_[timestamp].jpg)
[Speaker credentials and background]

---

## 💡 セミナーの核心メッセージ

### 1️⃣ [First Major Point]
![Relevant screenshot](screenshots/point1_[timestamp].jpg)
[Detailed explanation with data]

### 2️⃣ [Second Major Point]
[Continue pattern...]

---

## 💰 [Revenue/Results Section if applicable]
[Include specific numbers, comparisons, shocking statistics]

---

## 📈 成長ストーリー/事例
[Before/after narratives, transformation stories]

---

## ✅ 今すぐ実践すべきアクション
### 初心者向け
1. [Action item 1]
2. [Action item 2]

### 中級者向け
[Continue pattern...]

---

## 🎯 まとめ：成功への[N]つの鍵
[Final synthesis and takeaways]

---

## 📚 参考情報
- **動画時間**: [Duration]
- **作成日**: [Date]
```

## 🤖 Processing Workflow

### Phase 1: Initial Analysis
```python
def analyze_transcript(transcript_file):
    # 1. Load Whisper JSON
    segments = load_whisper_json(transcript_file)

    # 2. Identify speakers (if multiple voices detected)
    speakers = identify_speakers(segments)

    # 3. Detect topic boundaries
    topics = detect_topic_changes(segments)

    # 4. Score importance of each segment
    importance_scores = calculate_importance(segments)

    return processed_data
```

### Phase 2: Content Extraction
```python
def extract_key_content(processed_data):
    # 1. Extract shocking statistics
    statistics = find_statistics_and_numbers(processed_data)

    # 2. Identify success stories
    case_studies = extract_case_studies(processed_data)

    # 3. Find actionable advice
    action_items = extract_action_items(processed_data)

    # 4. Detect emotional peaks
    emotional_moments = find_emotional_peaks(processed_data)

    return content_elements
```

### Phase 3: Screenshot Selection
```python
def select_screenshot_moments(content_elements, max_screenshots=10):
    # 1. Score each moment
    scored_moments = []
    for moment in content_elements:
        score = calculate_screenshot_value(moment)
        scored_moments.append((moment, score))

    # 2. Select top moments with good distribution
    selected = select_with_distribution(scored_moments, max_screenshots)

    # 3. Generate screenshot commands
    screenshot_commands = generate_ffmpeg_commands(selected)

    return screenshot_commands
```

### Phase 4: Report Generation
```python
def generate_report(content_elements, screenshots):
    # 1. Use Gemini Ultimate Generator for high-quality summary
    summary = gemini_ultimate_generator.process(content_elements)

    # 2. Format with template
    report = format_markdown_report(summary, screenshots)

    # 3. Add visual enhancements (emojis, formatting)
    enhanced_report = enhance_visual_appeal(report)

    # 4. Validate quality score
    quality_score = validate_report_quality(enhanced_report)

    return enhanced_report if quality_score >= 95 else regenerate()
```

## 💎 Quality Assurance Criteria

### Content Quality Metrics
```yaml
metrics:
  executive_summary:
    - captures_essence: true
    - includes_key_number: true
    - compelling_hook: true

  structure:
    - logical_flow: true
    - clear_sections: true
    - balanced_content: true

  insights:
    - specific_examples: true
    - actionable_items: true
    - data_backed: true

  visuals:
    - strategic_screenshots: true
    - proper_formatting: true
    - emoji_enhancement: true
```

### Minimum Requirements
- ✅ Executive summary with bold key message
- ✅ At least 3 major sections with insights
- ✅ Specific numbers and statistics highlighted
- ✅ Action items categorized by level
- ✅ 5-10 strategic screenshots referenced
- ✅ Professional formatting with emojis
- ✅ Clear structure with headers and dividers

## 🔄 Integration with Existing Modules

### Use Existing Components
```python
# Leverage existing modules
from modules.transcriber import load_transcript
from modules.gemini_ultimate_generator import GeminiUltimateGenerator
from modules.reporter import MarkdownReporter
from modules.keyword_analyzer import KeywordAnalyzer

# For screenshot extraction
from modules.utils import extract_video_screenshots

# For quality validation
from modules.analyzer import ContentAnalyzer
```

### Memory Patterns
```python
# Store processing patterns for improvement
memory_keys = {
    "successful_templates": "report_templates/successful/",
    "topic_patterns": "memory/topic_patterns.json",
    "screenshot_criteria": "memory/screenshot_success.json",
    "quality_scores": "memory/report_quality_history.json"
}
```

## 🚀 Execution Commands

### Single Transcript Processing
```bash
python process_transcript.py --input output/transcripts/video.json \
                           --output output/reports/video_report.md \
                           --screenshots output/reports/screenshots/video/ \
                           --quality-target 100
```

### Batch Processing
```bash
python batch_process.py --input-dir output/transcripts/ \
                       --output-dir output/reports/ \
                       --parallel 4 \
                       --quality-check true
```

## 📊 Success Metrics

### Report Quality Indicators
1. **Comprehensiveness**: Covers all major topics from transcript
2. **Clarity**: Information is well-organized and easy to follow
3. **Actionability**: Includes specific, implementable advice
4. **Visual Appeal**: Professional formatting with strategic screenshots
5. **Engagement**: Compelling narrative that maintains reader interest

### Performance Targets
- Processing time: < 2 minutes per hour of transcript
- Quality score: ≥ 95/100
- Screenshot accuracy: ≥ 90% relevance
- Summary completeness: ≥ 95% key points captured

## 🎨 Formatting Guidelines

### Emoji Usage Map
```python
emoji_map = {
    "summary": "🎯",
    "profile": "👥",
    "idea": "💡",
    "money": "💰",
    "growth": "📈",
    "action": "✅",
    "important": "📌",
    "warning": "⚠️",
    "success": "🎉",
    "book": "📚",
    "time": "⏰",
    "world": "🌏"
}
```

### Emphasis Patterns
- **Bold** for key statements and shocking statistics
- *Italic* for quotes and citations
- `Code blocks` for formulas or specific methods
- > Blockquotes for critical insights
- --- Dividers between major sections

## 🔧 Troubleshooting

### Common Issues and Solutions
1. **Low quality score**: Increase Gemini token allocation
2. **Missing screenshots**: Check timestamp accuracy
3. **Poor structure**: Review topic clustering algorithm
4. **Incomplete summary**: Verify segment processing

## 📝 Implementation Notes

This CLAUDE.md defines a comprehensive system for transforming Whisper transcripts into professional reports. The system should:

1. **Prioritize Quality**: Use Gemini Ultimate Generator for maximum quality
2. **Be Intelligent**: Identify truly important moments, not just random samples
3. **Stay Consistent**: Follow the template while adapting to content
4. **Learn and Improve**: Use memory patterns to enhance over time
5. **Deliver Value**: Create reports that provide genuine insights and actionable advice

When processing any Whisper transcript, follow these guidelines to produce reports that match the excellence of the instagram_seminar_summary.md example.

---
*Version: 1.0 | Created: 2025-09-23 | Framework: VideoTranscriptAnalyzer*