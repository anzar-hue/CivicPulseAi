def main():
    import sys
    import os

    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    from app import app
    app.run(host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()