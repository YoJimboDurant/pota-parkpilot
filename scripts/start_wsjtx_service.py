#!/usr/bin/env python3

from parkpilot.services.wsjtx_service import load_config, run_service_loop


def main() -> None:
    cfg_dx = load_config()
    print("ParkPilot WSJT-X import service")
    print(f"ADIF file: {cfg_dx['adif_file']}")
    print(f"Polling every {cfg_dx['poll_seconds']} seconds")
    print("Press Ctrl+C to stop.\n")
    run_service_loop(cfg_dx)


if __name__ == "__main__":
    main()