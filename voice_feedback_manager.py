"""
voice_feedback_manager.py — Smart Voice Feedback Management
Provides context-aware, non-repetitive voice alerts for hazard detection.

Features:
- Message deduplication
- Smart cooldown management
- Priority-based announcement
- Accessibility-focused feedback
"""

import time
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
from queue import PriorityQueue


class FeedbackPriority(Enum):
    """Voice feedback priority levels."""
    LOW = 3       # Background information
    NORMAL = 2    # Standard alerts
    HIGH = 1      # Important warnings
    CRITICAL = 0  # Immediate danger


@dataclass
class VoiceFeedback:
    """Represents a voice feedback item."""
    message: str
    priority: FeedbackPriority
    unique_key: str
    cooldown: float  # Minimum seconds before repeating this message
    timestamp: float


class VoiceFeedbackManager:
    """
    Manages voice feedback to ensure accessibility-focused user experience.
    - Avoids overwhelming the user with too much speech
    - Maintains message variety
    - Implements smart cooldowns
    - Prioritizes critical information
    """

    # Message templates for common hazards
    MESSAGE_TEMPLATES = {
        "approaching_vehicle": "Warning: Vehicle is approaching quickly toward you.",
        "person_ahead": "Warning: Person is directly ahead of you. Move left or right.",
        "move_left": "Move slightly to your left for safety.",
        "move_right": "Move slightly to your right for safety.",
        "collision_risk": "Danger: Person or object directly ahead. Collision risk detected.",
        "road_work": "Warning: Road work detected. Workers and equipment ahead. Proceed with caution.",
        "fire_hazard": "Danger: Fire detected. Evacuate immediately.",
        "smoke_hazard": "Danger: Smoke detected. Emergency evacuation recommended.",
        "abnormal_motion": "Warning: Abnormal fast movement detected in your vicinity.",
        "crowded_area": "Warning: Crowded area detected with multiple people moving rapidly.",
    }

    def __init__(self, global_cooldown: float = 1.5):
        """
        Initialize the feedback manager.
        
        Args:
            global_cooldown: Minimum seconds between any two announcements
        """
        self.global_cooldown = global_cooldown
        self.feedback_queue: PriorityQueue = PriorityQueue()
        self.last_feedback_time: Dict[str, float] = {}
        self.feedback_history: List[VoiceFeedback] = []
        self.last_global_announcement_time = 0.0
        self.announced_hazards: Dict[str, float] = {}  # Track what was recently announced

    def add_feedback(
        self,
        message: str,
        unique_key: str,
        priority: FeedbackPriority = FeedbackPriority.NORMAL,
        cooldown: float = 3.0,
        force: bool = False,
    ) -> bool:
        """
        Add voice feedback to the queue.
        
        Args:
            message: The message to announce
            unique_key: Unique identifier for deduplication
            priority: How important this message is
            cooldown: Minimum seconds before this can be repeated
            force: If True, bypass cooldown checks for critical alerts
        
        Returns:
            True if feedback was queued, False if filtered due to cooldown
        """
        current_time = time.time()

        # Check global cooldown (prevent overwhelming user)
        if not force and (current_time - self.last_global_announcement_time < 0.5):
            return False

        # Check feedback-specific cooldown
        last_time = self.last_feedback_time.get(unique_key, 0)
        if not force and (current_time - last_time < cooldown):
            return False

        # Create feedback item
        feedback = VoiceFeedback(
            message=message,
            priority=priority,
            unique_key=unique_key,
            cooldown=cooldown,
            timestamp=current_time,
        )

        # Queue with priority (lower number = higher priority)
        self.feedback_queue.put((priority.value, current_time, unique_key, feedback))
        self.last_feedback_time[unique_key] = current_time
        self.last_global_announcement_time = current_time
        self.feedback_history.append(feedback)

        return True

    def get_next_feedback(self) -> Tuple[str, str]:
        """
        Get the next feedback message to announce.
        
        Returns:
            Tuple of (message, unique_key) or (None, None) if queue is empty
        """
        if self.feedback_queue.empty():
            return None, None

        priority, timestamp, unique_key, feedback = self.feedback_queue.get()
        return feedback.message, unique_key

    def hazard_to_feedback(
        self,
        hazard_type: str,
        level: int,
        location: str = "ahead",
        custom_message: str = None,
    ) -> Tuple[str, str, FeedbackPriority]:
        """
        Convert hazard information to voice feedback.
        
        Args:
            hazard_type: Type of hazard (e.g., "approaching_vehicle")
            level: Hazard level (0-3, higher = more critical)
            location: Where the hazard is ("left", "center", "right", "ahead")
            custom_message: Override default message
        
        Returns:
            Tuple of (message, unique_key, priority)
        """
        if custom_message:
            message = custom_message
        else:
            # Get base message from templates
            base_message = self.MESSAGE_TEMPLATES.get(
                hazard_type, f"Alert: {hazard_type.replace('_', ' ')}."
            )

            # Add directional information if not already included
            if location != "ahead" and "left" not in base_message and "right" not in base_message:
                if location == "left":
                    message = f"On the left: {base_message}"
                elif location == "right":
                    message = f"On the right: {base_message}"
                else:
                    message = base_message
            else:
                message = base_message

        # Determine priority
        if level >= 3:  # EMERGENCY
            priority = FeedbackPriority.CRITICAL
            unique_key = f"emergency_{hazard_type}"
            cooldown = 1.0
        elif level == 2:  # DANGER
            priority = FeedbackPriority.HIGH
            unique_key = f"danger_{hazard_type}"
            cooldown = 2.0
        elif level == 1:  # WARNING
            priority = FeedbackPriority.NORMAL
            unique_key = f"warning_{hazard_type}"
            cooldown = 3.0
        else:  # INFO
            priority = FeedbackPriority.LOW
            unique_key = f"info_{hazard_type}"
            cooldown = 5.0

        return message, unique_key, priority

    def should_announce(self, unique_key: str, cooldown: float = 2.0) -> bool:
        """
        Check if enough time has passed to announce this feedback again.
        """
        current_time = time.time()
        last_time = self.last_feedback_time.get(unique_key, 0)
        return (current_time - last_time) > cooldown

    def mark_announced(self, unique_key: str) -> None:
        """Mark a feedback as announced."""
        self.last_feedback_time[unique_key] = time.time()

    def get_pending_feedback_count(self) -> int:
        """Get number of pending feedback items in queue."""
        return self.feedback_queue.qsize()

    def clear_queue(self) -> None:
        """Clear all pending feedback (useful for emergency interrupts)."""
        self.feedback_queue = PriorityQueue()

    def get_feedback_stats(self) -> Dict:
        """Get statistics about feedback generation."""
        return {
            "total_feedback_generated": len(self.feedback_history),
            "pending_in_queue": self.get_pending_feedback_count(),
            "unique_messages_tracked": len(self.last_feedback_time),
            "last_announcement_time": self.last_global_announcement_time,
        }

    def is_quiet_mode(self) -> bool:
        """
        Check if we're in quiet mode (very little feedback needed).
        This can be toggled based on user preference or environment state.
        """
        # Implement logic to detect if user is stationary and safe
        return False  # Can be extended


class AccessibilityFilter:
    """
    Post-process feedback to ensure accessibility best practices.
    - Keep messages short (under 10 words)
    - Make them actionable
    - Avoid jargon
    """

    MAX_MESSAGE_LENGTH = 100  # Characters
    MAX_WORDS = 10

    @staticmethod
    def is_accessible(message: str) -> bool:
        """Check if message follows accessibility guidelines."""
        # Check word count
        words = message.split()
        if len(words) > AccessibilityFilter.MAX_WORDS:
            return False

        # Check character count
        if len(message) > AccessibilityFilter.MAX_MESSAGE_LENGTH:
            return False

        # Check for complex terminology
        jargon = ["algorithm", "detection", "confidence", "threshold", "metadata"]
        if any(term in message.lower() for term in jargon):
            return False

        return True

    @staticmethod
    def simplify_message(message: str) -> str:
        """Simplify message to meet accessibility standards."""
        # Remove percentage signs and technical details
        message = message.replace("%", "")

        # Keep only first sentence if message is too long
        if len(message.split()) > AccessibilityFilter.MAX_WORDS:
            first_sentence = message.split(".")[0]
            if len(first_sentence.split()) <= AccessibilityFilter.MAX_WORDS:
                return first_sentence + "."

        return message

    @staticmethod
    def get_alternative(message: str, context: str = "") -> str:
        """Get a simpler alternative message."""
        simple_versions = {
            "approaching": "coming toward you",
            "detected": "found",
            "abnormal": "unusual",
            "hazard": "danger",
        }

        result = message
        for technical, simple in simple_versions.items():
            result = result.replace(technical, simple)

        return result.capitalize()
