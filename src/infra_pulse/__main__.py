from infra_pulse.simulate import run_demo

if __name__ == "__main__":
    data = run_demo()
    print(data["summary"])
