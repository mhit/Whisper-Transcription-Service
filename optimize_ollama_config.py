#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama Configuration Optimizer
GPU-aware context size and parameter tuning for maximum quality
"""

import json
import requests
import logging
from typing import Dict, Any
import subprocess
import time

class OllamaOptimizer:
    """Ollama configuration optimizer for quality improvement"""

    def __init__(self, api_base_url: str = "http://192.168.43.245:11434"):
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(__name__)

    def check_current_models(self) -> list:
        """Check available models and their configurations"""
        try:
            response = requests.get(f"{self.api_base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                return models
            return []
        except Exception as e:
            self.logger.error(f"Failed to get models: {e}")
            return []

    def test_model_performance(self, model_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test model performance with different configurations"""
        test_prompt = """
        Analyze the following business metrics and provide strategic insights:
        - Revenue: $2,226,560
        - Profit margin: 31.3%
        - Customer acquisition cost: $501
        - Monthly growth rate: 15%

        Provide:
        1. Three key insights with specific numbers
        2. Strategic recommendations with ROI projections
        3. Risk analysis with mitigation strategies
        """

        payload = {
            "model": model_name,
            "prompt": test_prompt,
            "stream": False,
            "options": config
        }

        start_time = time.time()

        try:
            response = requests.post(
                f"{self.api_base_url}/api/generate",
                json=payload,
                timeout=120
            )

            end_time = time.time()

            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')

                # Evaluate response quality
                quality_score = self._evaluate_response_quality(response_text)

                return {
                    'success': True,
                    'model': model_name,
                    'config': config,
                    'response_length': len(response_text),
                    'response_time': end_time - start_time,
                    'quality_score': quality_score,
                    'response_preview': response_text[:500]
                }
            else:
                return {
                    'success': False,
                    'error': f"Status {response.status_code}"
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _evaluate_response_quality(self, response: str) -> float:
        """Simple quality evaluation based on response characteristics"""
        score = 0.0

        # Check for structure
        if "1." in response and "2." in response and "3." in response:
            score += 20

        # Check for numbers/data
        import re
        numbers = re.findall(r'\d+[,.]?\d*', response)
        if len(numbers) > 5:
            score += 20

        # Check for business terminology
        business_terms = ['ROI', 'margin', 'revenue', 'cost', 'growth', 'strategy', 'risk', 'profit']
        term_count = sum(1 for term in business_terms if term.lower() in response.lower())
        score += min(term_count * 5, 30)

        # Check for depth (response length)
        if len(response) > 1500:
            score += 20
        elif len(response) > 1000:
            score += 10

        # Check for clear sections
        if response.count('\n\n') > 3:
            score += 10

        return min(score, 100)

    def optimize_for_gpu(self, gpu_memory_gb: int = 16) -> Dict[str, Any]:
        """Recommend optimal configuration based on GPU memory"""

        configs = {
            8: {
                'num_ctx': 4096,
                'num_batch': 512,
                'num_gpu': 99,
                'temperature': 0.3,
                'top_k': 40,
                'top_p': 0.9,
                'repeat_penalty': 1.1,
                'num_predict': 2048
            },
            16: {
                'num_ctx': 8192,
                'num_batch': 1024,
                'num_gpu': 99,
                'temperature': 0.3,
                'top_k': 50,
                'top_p': 0.9,
                'repeat_penalty': 1.1,
                'num_predict': 4096
            },
            24: {
                'num_ctx': 16384,
                'num_batch': 2048,
                'num_gpu': 99,
                'temperature': 0.3,
                'top_k': 60,
                'top_p': 0.95,
                'repeat_penalty': 1.05,
                'num_predict': 8192
            },
            32: {
                'num_ctx': 32768,
                'num_batch': 4096,
                'num_gpu': 99,
                'temperature': 0.3,
                'top_k': 80,
                'top_p': 0.95,
                'repeat_penalty': 1.05,
                'num_predict': 16384
            }
        }

        # Find closest configuration
        available_configs = sorted(configs.keys())
        selected = 8
        for config_size in available_configs:
            if gpu_memory_gb >= config_size:
                selected = config_size

        return configs[selected]

    def run_optimization_test(self, gpu_memory_gb: int = 16):
        """Run comprehensive optimization test"""
        self.logger.info("="*60)
        self.logger.info("Ollama Configuration Optimization Test")
        self.logger.info("="*60)

        # Get available models
        models = self.check_current_models()
        self.logger.info(f"Available models: {[m['name'] for m in models]}")

        # Get optimal configuration
        optimal_config = self.optimize_for_gpu(gpu_memory_gb)
        self.logger.info(f"\nOptimal configuration for {gpu_memory_gb}GB GPU:")
        for key, value in optimal_config.items():
            self.logger.info(f"  {key}: {value}")

        # Test each model with optimal configuration
        results = []

        # Priority order: larger models first
        model_priority = ['qwen2.5:32b', 'qwen3:30b', 'gpt-oss:20b']

        for model_name in model_priority:
            if any(m['name'] == model_name for m in models):
                self.logger.info(f"\nTesting {model_name}...")
                result = self.test_model_performance(model_name, optimal_config)

                if result['success']:
                    self.logger.info(f"  Quality score: {result['quality_score']:.1f}/100")
                    self.logger.info(f"  Response time: {result['response_time']:.1f}s")
                    self.logger.info(f"  Response length: {result['response_length']} chars")
                    results.append(result)
                else:
                    self.logger.error(f"  Failed: {result.get('error', 'Unknown error')}")

        # Find best performing configuration
        if results:
            best = max(results, key=lambda x: x['quality_score'])
            self.logger.info("\n" + "="*60)
            self.logger.info("BEST CONFIGURATION")
            self.logger.info("="*60)
            self.logger.info(f"Model: {best['model']}")
            self.logger.info(f"Quality Score: {best['quality_score']:.1f}/100")
            self.logger.info(f"Configuration:")
            for key, value in best['config'].items():
                self.logger.info(f"  {key}: {value}")

            return best

        return None


def main():
    """Main execution"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create optimizer
    optimizer = OllamaOptimizer()

    # Run optimization test
    # Adjust GPU memory based on your system
    # Common values: 8, 16, 24, 32
    gpu_memory = 16  # Change this based on your GPU

    print(f"\nOptimizing for {gpu_memory}GB GPU...")
    best_config = optimizer.run_optimization_test(gpu_memory)

    if best_config:
        print("\n" + "="*60)
        print("RECOMMENDED SETTINGS FOR ULTIMATE REPORT GENERATION")
        print("="*60)
        print(f"""
Update your report generator with these settings:

config = {{
    'api_base_url': 'http://192.168.43.245:11434',
    'model': '{best_config['model']}',
    'options': {json.dumps(best_config['config'], indent=4)}
}}

Expected quality improvement: +{best_config['quality_score'] - 80:.1f} points
        """)


if __name__ == "__main__":
    main()