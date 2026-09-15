#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ihale-mcp",
    version="1.0.0",
    author="İhale MCP Contributors",
    description="MCP Server for Turkish Government Tenders (İhale)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/ihale-mcp",
    py_modules=["ihale_mcp", "ihale_client", "ilan_client", "ihale_models", "ekap_verification"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "ihale-mcp=ihale_mcp:main",
        ],
    },
)