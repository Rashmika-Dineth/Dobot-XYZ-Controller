
import pygame
import time

DEAD_ZONE = 0.15
POLL_INTERVAL = 0.05
RECONNECT_DELAY = 1.0

pygame.init()
pygame.joystick.init()

joy = None


def connect_joystick():
    """Try to connect to the first available joystick."""
    global joy

    count = pygame.joystick.get_count()

    if count == 0:
        print("\nWaiting for controller...")
        return False

    try:
        # Create a new object; don't reuse a closed object
        candidate = pygame.joystick.Joystick(0)

        print(
            f"\nConnected: {candidate.get_name()} | "
            f"Axes: {candidate.get_numaxes()} | "
            f"Buttons: {candidate.get_numbuttons()}"
        )

        joy = candidate
        return True

    except pygame.error as e:
        print(f"\nController not ready: {e}")
        joy = None
        return False


try:
    print("Waiting for Nintendo Switch Pro Controller...")

    while not connect_joystick():
        pygame.event.pump()
        time.sleep(RECONNECT_DELAY)

    while True:
        events = pygame.event.get()
        disconnected = False

        for event in events:
            if event.type == pygame.JOYDEVICEREMOVED:
                print("\nController disconnected.")
                disconnected = True

        if disconnected:
            joy = None

            # Give Windows/SDL time to update device status
            time.sleep(RECONNECT_DELAY)

            while not connect_joystick():
                pygame.event.pump()
                time.sleep(RECONNECT_DELAY)

            continue

        # Device-added events are informational here.
        # Do not reopen an already working controller.
        if joy is None or not joy.get_init():
            time.sleep(RECONNECT_DELAY)
            continue

        try:
            raw_axes = [
                joy.get_axis(i)
                for i in range(joy.get_numaxes())
            ]

            filtered_axes = [
                0.0 if abs(v) < DEAD_ZONE else round(v, 2)
                for v in raw_axes
            ]

            buttons = [
                i for i in range(joy.get_numbuttons())
                if joy.get_button(i)
            ]

            print(
                f"\rRaw: {[round(v, 2) for v in raw_axes]} | "
                f"Filtered: {filtered_axes} | "
                f"Buttons: {buttons}    ",
                end="",
                flush=True
            )

        except pygame.error as e:
            print(f"\nController read error: {e}")
            joy = None
            time.sleep(RECONNECT_DELAY)

        time.sleep(POLL_INTERVAL)

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    pygame.quit()
    print("Pygame closed.")