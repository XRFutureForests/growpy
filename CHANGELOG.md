# Changelog

All notable changes to The Grove project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- FBX export workflow with Nanite assembly support for Unreal Engine 5
- USD export with proper coordinate system (Z-up) and unit scaling
- Twig coordinate system fixes for proper placement in USD/FBX
- Species asset lookup system with comprehensive tree asset database
- Growth model generation for multi-species forest simulation
- Five-step pipeline for complete tree generation workflow
- Bark texture integration with proper material assignment
- Mount point system for twig attachment in USD exports

### Fixed

- Coordinate system alignment between The Grove, FBX, and USD formats
- Twig placement and rotation in exported models
- USD scale factor (centimeters to meters conversion)
- Bark texture lookup and assignment in materials
- Asset path resolution for cross-platform compatibility

### Changed

- Refactored documentation structure (moved summaries to archive)
- Consolidated temporary fix documentation into proper changelog
- Improved code organization following project template standards

### Documentation

- Complete user guides for Unreal Engine Nanite workflow
- Species library generation guide
- USD export with twigs documentation
- Nanite assembly integration guide
- Quick reference guides for common workflows

## Archive

Historical development summaries and fix documentation have been archived in `docs/archive/` for reference.
