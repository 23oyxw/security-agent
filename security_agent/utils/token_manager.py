"""Token管理器 - 支持Token计数和上下文压缩"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TokenStats:
    """Token统计信息"""
    total_tokens: int = 0
    system_tokens: int = 0
    history_tokens: int = 0
    context_tokens: int = 0
    is_over_limit: bool = False
    compression_ratio: float = 1.0


class TokenManager:
    """Token管理器，支持Token计数和上下文压缩"""
    
    def __init__(self, max_tokens: int = 128000, reserve_tokens: int = 4000):
        """
        初始化Token管理器
        
        Args:
            max_tokens: 最大Token数（默认128K，适用于GPT-4）
            reserve_tokens: 保留Token数（用于输出）
        """
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.context_limit = max_tokens - reserve_tokens
    
    def count_tokens(self, text: str) -> int:
        """
        估算Token数量（简化版本，基于字符数估算）
        
        注意：这是简化版本，实际项目可以使用tiktoken库
        
        Args:
            text: 文本
            
        Returns:
            估算的Token数量
        """
        if not text:
            return 0
        
        # 简单估算：中文字符约1.5个Token，英文字符约0.25个Token
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z0-9]', text))
        other_chars = len(text) - chinese_chars - english_chars
        
        return int(chinese_chars * 1.5 + english_chars * 0.25 + other_chars * 0.5)
    
    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        计算消息列表的Token数量
        
        Args:
            messages: 消息列表
            
        Returns:
            Token总数
        """
        total = 0
        for msg in messages:
            # 每条消息有固定开销
            total += 4  # 消息格式开销
            total += self.count_tokens(msg.get("content", ""))
            total += self.count_tokens(msg.get("role", ""))
        return total
    
    def analyze_context(self, messages: List[Dict[str, str]]) -> TokenStats:
        """
        分析上下文Token使用情况
        
        Args:
            messages: 消息列表
            
        Returns:
            Token统计信息
        """
        stats = TokenStats()
        
        if not messages:
            return stats
        
        # 分析每条消息
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content", "")
            tokens = self.count_tokens(content) + 4
            
            if i == 0 and role == "system":
                stats.system_tokens += tokens
            elif role in ["user", "assistant"]:
                stats.history_tokens += tokens
            else:
                stats.context_tokens += tokens
        
        stats.total_tokens = stats.system_tokens + stats.history_tokens + stats.context_tokens
        stats.is_over_limit = stats.total_tokens > self.context_limit
        
        return stats
    
    def compress_messages(self, messages: List[Dict[str, str]], 
                         target_tokens: Optional[int] = None) -> List[Dict[str, str]]:
        """
        压缩消息列表以符合Token限制
        
        Args:
            messages: 原始消息列表
            target_tokens: 目标Token数（默认为context_limit的80%）
            
        Returns:
            压缩后的消息列表
        """
        if not messages:
            return messages
        
        if target_tokens is None:
            target_tokens = int(self.context_limit * 0.8)
        
        stats = self.analyze_context(messages)
        
        if stats.total_tokens <= target_tokens:
            # 不需要压缩
            return messages
        
        # 计算压缩比例
        compression_ratio = target_tokens / stats.total_tokens
        
        # 保留system消息
        system_msgs = [msg for msg in messages if msg.get("role") == "system"]
        other_msgs = [msg for msg in messages if msg.get("role") != "system"]
        
        if not other_msgs:
            return messages
        
        # 计算system消息Token数
        system_tokens = self.count_messages_tokens(system_msgs)
        available_tokens = target_tokens - system_tokens
        
        if available_tokens <= 0:
            # System消息已经超过限制，只返回system消息
            return system_msgs
        
        # 压缩其他消息
        compressed_msgs = []
        current_tokens = 0
        
        # 从最新的消息开始保留
        for msg in reversed(other_msgs):
            msg_tokens = self.count_messages_tokens([msg])
            
            if current_tokens + msg_tokens <= available_tokens:
                compressed_msgs.insert(0, msg)
                current_tokens += msg_tokens
            else:
                # 尝试压缩这条消息
                compressed_content = self._compress_content(msg.get("content", ""), 
                                                           available_tokens - current_tokens)
                if compressed_content:
                    compressed_msg = msg.copy()
                    compressed_msg["content"] = compressed_content
                    compressed_msgs.insert(0, compressed_msg)
                break
        
        # 合并结果
        result = system_msgs + compressed_msgs
        
        # 更新压缩比例
        final_stats = self.analyze_context(result)
        if stats.total_tokens > 0:
            final_stats.compression_ratio = final_stats.total_tokens / stats.total_tokens
        
        return result
    
    def _compress_content(self, content: str, max_tokens: int) -> str:
        """
        压缩单条消息内容
        
        Args:
            content: 原始内容
            max_tokens: 最大Token数
            
        Returns:
            压缩后的内容
        """
        if not content:
            return content
        
        current_tokens = self.count_tokens(content)
        
        if current_tokens <= max_tokens:
            return content
        
        # 简单压缩：截断内容
        # 计算目标字符数（简化估算）
        target_chars = int(max_tokens * 2)  # 粗略估算：1 Token ≈ 2 字符
        
        if len(content) > target_chars:
            # 保留开头和结尾
            keep_chars = target_chars // 2
            compressed = content[:keep_chars] + "\n...[内容已压缩]...\n" + content[-keep_chars:]
            return compressed
        
        return content
    
    def should_compress(self, messages: List[Dict[str, str]]) -> bool:
        """
        判断是否需要压缩
        
        Args:
            messages: 消息列表
            
        Returns:
            是否需要压缩
        """
        stats = self.analyze_context(messages)
        return stats.is_over_limit
    
    def get_compression_suggestions(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        获取压缩建议
        
        Args:
            messages: 消息列表
            
        Returns:
            压缩建议
        """
        stats = self.analyze_context(messages)
        
        suggestions = {
            "needs_compression": stats.is_over_limit,
            "current_tokens": stats.total_tokens,
            "context_limit": self.context_limit,
            "usage_percentage": round(stats.total_tokens / self.context_limit * 100, 2),
            "suggestions": []
        }
        
        if stats.is_over_limit:
            overflow = stats.total_tokens - self.context_limit
            
            if stats.history_tokens > overflow * 2:
                suggestions["suggestions"].append({
                    "type": "compress_history",
                    "description": f"压缩历史对话，可节省约{stats.history_tokens // 2}个Token",
                    "priority": "high"
                })
            
            if len(messages) > 10:
                suggestions["suggestions"].append({
                    "type": "reduce_messages",
                    "description": f"减少消息数量（当前{len(messages)}条）",
                    "priority": "medium"
                })
            
            suggestions["suggestions"].append({
                "type": "summarize",
                "description": "对历史对话进行摘要",
                "priority": "high"
            })
        
        return suggestions


# 全局单例
_manager_instance: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """获取全局Token管理器实例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = TokenManager()
    return _manager_instance
