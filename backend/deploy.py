import os
import shutil
import zipfile
import subprocess

# Top-level Python source files to include in the Lambda package.
# All sub-packages (directories containing __init__.py) are included automatically.
_SOURCE_FILES = [
    "city_chat_tool_dispatch.py",
    "city_chat_tools.py",
    "city_chat_tools_schema.py",
    "city_context.py",
    "city_scenario_schema.py",
    "city_simulation.py",
    "city_tools.py",
    "context.py",
    "database.py",
    "finance_tools.py",
    "lambda_handler.py",
    "pathfinding.py",
    "redis_bus.py",
    "resources.py",
    "server.py",
    "simulation.py",
]

# Sub-packages (directories that contain an __init__.py) to copy wholesale.
_SOURCE_PACKAGES = [
    "agents",
    "finance",
    "memory",
]


def main():
    print("Creating Lambda deployment package...")

    # Clean up
    if os.path.exists("lambda-package"):
        shutil.rmtree("lambda-package")
    if os.path.exists("lambda-deployment.zip"):
        os.remove("lambda-deployment.zip")

    # Create package directory
    os.makedirs("lambda-package")

    # Install dependencies using Docker with Lambda runtime image
    print("Installing dependencies for Lambda runtime...")

    # Use the official AWS Lambda Python 3.12 image
    # This ensures compatibility with Lambda's runtime environment
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{os.getcwd()}:/var/task",
            "--platform",
            "linux/amd64",  # Force x86_64 architecture
            "--entrypoint",
            "",  # Override the default entrypoint
            "public.ecr.aws/lambda/python:3.12",
            "/bin/sh",
            "-c",
            "pip install --target /var/task/lambda-package -r /var/task/requirements.txt --upgrade",
        ],
        check=True,
    )

    # Copy application source files
    print("Copying application files...")
    for file in _SOURCE_FILES:
        if os.path.exists(file):
            shutil.copy2(file, "lambda-package/")
        else:
            print(f"  ⚠ Warning: source file not found: {file}")

    # Copy application sub-packages
    for pkg in _SOURCE_PACKAGES:
        if os.path.isdir(pkg):
            shutil.copytree(pkg, f"lambda-package/{pkg}")
        else:
            print(f"  ⚠ Warning: source package not found: {pkg}/")

    # Copy data directory
    if os.path.exists("data"):
        shutil.copytree("data", "lambda-package/data")

    # Create zip
    print("Creating zip file...")
    with zipfile.ZipFile("lambda-deployment.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("lambda-package"):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, "lambda-package")
                zipf.write(file_path, arcname)

    # Show package sizes
    zip_size_mb = os.path.getsize("lambda-deployment.zip") / (1024 * 1024)
    # Estimate unzipped size from the package directory
    unzipped_bytes = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk("lambda-package")
        for f in files
    )
    unzipped_mb = unzipped_bytes / (1024 * 1024)
    print(f"✓ Created lambda-deployment.zip ({zip_size_mb:.2f} MB zipped, {unzipped_mb:.2f} MB unzipped)")


if __name__ == "__main__":
    main()