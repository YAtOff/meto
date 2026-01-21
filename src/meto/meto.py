from prompt_toolkit import prompt


def main():
    while True:
        user_input = prompt(">>> ")
        print(f"You said: {user_input}")


if __name__ == "__main__":
    main()
