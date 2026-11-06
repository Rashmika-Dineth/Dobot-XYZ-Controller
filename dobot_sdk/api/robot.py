# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""
Main Robot Controller
Integrates all modules and provides a unified control interface.
"""

import threading
import time
import logging
from typing import Optional, Callable
from ..core.connection import DobotConnection
from ..protocol.feedback import FeedbackParser
from ..models.status import RobotStatus
from .motion import Motion, CoordinateType
from .io import IO
from .communication import Communication
from .plugins import Plugins
from .robot_control import RobotControl
from .error_controller import ErrorController

logger = logging.getLogger("dobot_sdk")


class DobotRobot:
    """
    Main controller class for Dobot robots.

    Example:
        with DobotRobot("192.168.1.100") as robot:
            robot.robot_control.EnableRobot()
            pose = [400, 0, 300, 180, 0, 0]
            robot.motion.MovJ(pose, CoordinateType.CARTESIAN)
    """

    def __init__(
        self,
        ip: str,
        dashboard_port: int = 29999,
        feedback_port: int = 30004,
        feedback_port_30005: int = None,
        feedback_port_30006: int = None,
        connect_timeout: float = 5.0,
        receive_timeout: float = 10.0
    ):
        """
        Initialize the robot object.

        Args:
            ip: Robot IP address.
            dashboard_port: Dashboard port (default: 29999).
            feedback_port: Feedback port (default: 30004).
                - 30004: Real-time feedback, every 8 ms.
                - 30005: Configuration feedback, every 200 ms.
                - 30006: Configuration feedback, every 1000 ms.
            feedback_port_30005: Optional second feedback port (default: None).
            feedback_port_30006: Optional third feedback port (default: None).
            connect_timeout: Connection timeout in seconds (default: 5 seconds).
            receive_timeout: Receive timeout in seconds (default: 10 seconds).
        """
        self.ip = ip
        self._connect_timeout = connect_timeout
        self._receive_timeout = receive_timeout

        # Dashboard connection
        self._dashboard_conn = DobotConnection(ip, dashboard_port)
        self._dashboard_conn.set_timeout(connect_timeout, receive_timeout)

        # Feedback connection
        self._feedback_conn = DobotConnection(ip, feedback_port)
        self._feedback_conn.set_timeout(connect_timeout, receive_timeout)

        # Optional additional feedback port connections
        self._feedback_conn_30005 = None
        if feedback_port_30005:
            self._feedback_conn_30005 = DobotConnection(
                ip, feedback_port_30005
            )
            self._feedback_conn_30005.set_timeout(
                connect_timeout, receive_timeout
            )

        self._feedback_conn_30006 = None
        if feedback_port_30006:
            self._feedback_conn_30006 = DobotConnection(
                ip, feedback_port_30006
            )
            self._feedback_conn_30006.set_timeout(
                connect_timeout, receive_timeout
            )

        # Protocol parser (used only for feedback)
        self._feedback_parser = FeedbackParser()

        # Five modules
        self.motion = Motion(self._dashboard_conn)  # Motion module
        self.io = IO(self._dashboard_conn)  # I/O module
        self.communication = Communication(
            self._dashboard_conn
        )  # Communication module
        self.plugins = Plugins(self._dashboard_conn)  # Plugin module
        self.robot_control = RobotControl(
            self._dashboard_conn
        )  # Robot control module
        self.error = ErrorController(ip)  # Error controller module

        # Status monitoring
        self._latest_status: Optional[RobotStatus] = None
        self._feedback_thread: Optional[threading.Thread] = None
        self._feedback_running = False
        self._callback: Optional[Callable] = None

        # Connection status callback
        self._connection_callback: Optional[Callable[[bool], None]] = None

    def SetTimeout(
        self,
        connect_timeout: float = None,
        receive_timeout: float = None
    ):
        """
        Set connection and receive timeouts.

        Args:
            connect_timeout: Connection timeout in seconds.
            receive_timeout: Receive timeout in seconds.
        """
        self._dashboard_conn.set_timeout(
            connect_timeout, receive_timeout
        )
        self._feedback_conn.set_timeout(
            connect_timeout, receive_timeout
        )

        if self._feedback_conn_30005:
            self._feedback_conn_30005.set_timeout(
                connect_timeout, receive_timeout
            )

        if self._feedback_conn_30006:
            self._feedback_conn_30006.set_timeout(
                connect_timeout, receive_timeout
            )

        if connect_timeout is not None:
            self._connect_timeout = connect_timeout

        if receive_timeout is not None:
            self._receive_timeout = receive_timeout

    def EnableAutoReconnect(
        self,
        enable: bool = True,
        callback: Callable[[bool], None] = None
    ):
        """
        Enable or disable automatic reconnection.

        Args:
            enable: Whether to enable automatic reconnection.
            callback: Callback invoked when the connection status changes.
                      Receives a Boolean indicating the connection status:
                      True: Connected successfully.
                      False: Connection disconnected.
        """
        self._connection_callback = callback

        def connection_status_handler(is_connected: bool):
            status = "connected" if is_connected else "disconnected"
            logger.info(f"Robot connection status changed: {status}")

            if self._connection_callback:
                try:
                    self._connection_callback(is_connected)
                except Exception as e:
                    logger.error(
                        f"Connection status callback failed: {str(e)}"
                    )

        self._dashboard_conn.enable_auto_reconnect(
            enable, connection_status_handler
        )
        self._feedback_conn.enable_auto_reconnect(
            enable, connection_status_handler
        )

        if self._feedback_conn_30005:
            self._feedback_conn_30005.enable_auto_reconnect(
                enable, connection_status_handler
            )

        if self._feedback_conn_30006:
            self._feedback_conn_30006.enable_auto_reconnect(
                enable, connection_status_handler
            )

        status = "enabled" if enable else "disabled"
        logger.info(f"Automatic reconnection {status}")

    def Connect(self, timeout: float = None):
        """
        Connect to the robot.

        Args:
            timeout: Connection timeout in seconds.
                     Defaults to the timeout configured during initialization.
        """
        actual_timeout = (
            timeout if timeout is not None else self._connect_timeout
        )

        logger.info(f"Connecting to robot {self.ip}...")

        self._dashboard_conn.connect(actual_timeout)
        self._feedback_conn.connect(actual_timeout)

        # Connect to optional additional feedback ports
        if self._feedback_conn_30005:
            self._feedback_conn_30005.connect(actual_timeout)

        if self._feedback_conn_30006:
            self._feedback_conn_30006.connect(actual_timeout)

        logger.info(f"Robot connected successfully: {self.ip}")

    @property
    def IsConnected(self) -> bool:
        """
        Check the robot connection status.

        Returns:
            bool: True if connected, False otherwise.
        """
        return (
            self._dashboard_conn.is_connected
            and self._feedback_conn.is_connected
            and (
                not self._feedback_conn_30005
                or self._feedback_conn_30005.is_connected
            )
            and (
                not self._feedback_conn_30006
                or self._feedback_conn_30006.is_connected
            )
        )

    def Disconnect(self):
        """Disconnect from the robot."""
        self.StopFeedbackMonitor()
        self._dashboard_conn.disconnect()
        self._feedback_conn.disconnect()

        # Disconnect optional additional feedback ports
        if self._feedback_conn_30005:
            self._feedback_conn_30005.disconnect()

        if self._feedback_conn_30006:
            self._feedback_conn_30006.disconnect()

        logger.info(f"Robot disconnected: {self.ip}")

    def GetStatus(self) -> Optional[RobotStatus]:
        """
        Get the latest robot status.

        Returns:
            RobotStatus: Latest robot status, or None if monitoring
                         has not been started.
        """
        return self._latest_status

    def StartFeedbackMonitor(self, callback: Callable = None):
        """
        Start the status feedback monitoring thread.

        Args:
            callback: Status update callback that receives a RobotStatus
                      object as its argument.
        """
        if self._feedback_running:
            return

        self._callback = callback
        self._feedback_running = True

        self._feedback_thread = threading.Thread(
            target=self._feedback_loop,
            daemon=True
        )
        self._feedback_thread.start()

        logger.info("Status monitoring started")

    def StopFeedbackMonitor(self):
        """Stop status feedback monitoring."""
        self._feedback_running = False

        if self._feedback_thread:
            self._feedback_thread.join(timeout=2.0)
            self._feedback_thread = None

        logger.info("Status monitoring stopped")

    def _feedback_loop(self):
        """Feedback data reception loop."""
        while self._feedback_running:
            try:
                # Receive raw bytes
                raw = self._feedback_conn.receive_bytes(144000)

                # Handle potentially concatenated packets
                if len(raw) > 1440:
                    raw = self._feedback_conn.receive_bytes(144000)

                if len(raw) < 1440:
                    time.sleep(0.01)
                    continue

                # Extract 1440 bytes
                packet = raw[:1440]

                # Parse the packet
                status = self._feedback_parser.parse(packet)

                if status:
                    self._latest_status = status

                    # Invoke the callback
                    if self._callback:
                        try:
                            self._callback(status)
                        except Exception as e:
                            logger.error(
                                f"Callback error: {e}",
                                exc_info=True
                            )

            except Exception as e:
                logger.error(
                    f"Feedback error: {e}",
                    exc_info=True
                )
                time.sleep(0.1)

    def __enter__(self):
        """Context manager entry."""
        self.Connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.Disconnect()
        return False

    def GetError(self, language: str = "zh_cn") -> dict:
        """
        Get robot alarm information through the HTTP interface.

        Args:
            language: Language setting. Supported languages:
                "zh_cn"   - Simplified Chinese
                "zh_hant" - Traditional Chinese
                "en"      - English
                "ja"      - Japanese
                "de"      - German
                "vi"      - Vietnamese
                "es"      - Spanish
                "fr"      - French
                "ko"      - Korean
                "ru"      - Russian

        Returns:
            dict: Dictionary containing alarm information, with the
                  following structure:
            {
                "errMsg": [
                    {
                        "id": xxx,
                        "level": xxx,
                        "description": "xxx",
                        "solution": "xxx",
                        "mode": "xxx",
                        "date": "xxxx",
                        "time": "xxxx"
                    }
                ]
            }

            Returns {"errMsg": []} if there are no alarms.
        """
        return self.error.GetError(language)

    def GetErrorFormatted(self, language: str = "en") -> str:
        """
        Get formatted robot alarm information through the HTTP interface.

        Args:
            language: Language setting.

        Returns:
            str: Formatted alarm information string.
        """
        return self.error.GetErrorFormatted(language)

    def __del__(self):
        """Destructor."""
        self.Disconnect()

    # Backward-compatible aliases (snake_case -> PascalCase)
    set_timeout = SetTimeout
    enable_auto_reconnect = EnableAutoReconnect
    connect = Connect
    disconnect = Disconnect
    get_status = GetStatus
    start_feedback_monitor = StartFeedbackMonitor
    stop_feedback_monitor = StopFeedbackMonitor
    get_error = GetError
    get_error_formatted = GetErrorFormatted

    @property
    def is_connected(self):
        return self.IsConnected