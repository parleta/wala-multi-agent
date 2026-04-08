#!/bin/bash

# AZTM Regression Test Runner
# Runs regression tests locally with Docker support for XMPP server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OPENFIRE_CONTAINER="aztm-test-openfire"
OPENFIRE_IMAGE="quantumobject/docker-openfire:latest"
XMPP_PORT=5222
ADMIN_PORT=9090
TEST_TIMEOUT=300

# Default values
KEEP_RUNNING=false
RUN_COVERAGE=true
TEST_PATTERN=""
PYTEST_ARGS=""
TEST_TYPE="all"
DEBUG=false
SKIP_DOCKER=false

# Parse command line arguments
print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -k, --keep          Keep services running after tests"
    echo "  -s, --skip-docker   Skip Docker/integration tests"
    echo "  -t, --type TYPE     Test type: unit, integration, performance, all (default: all)"
    echo "  -p, --pattern PAT   Test pattern to match (pytest -k)"
    echo "  -d, --debug         Enable debug output"
    echo "  -n, --no-coverage   Disable coverage reporting"
    echo "  -c, --clean         Clean up Docker containers before starting"
    echo "  -v, --verbose       Verbose pytest output"
    echo ""
    echo "Examples:"
    echo "  $0                           # Run all tests"
    echo "  $0 -t unit                   # Run only unit tests"
    echo "  $0 -t integration -k login   # Run integration tests matching 'login'"
    echo "  $0 -k connectivity -d        # Run tests matching 'connectivity' with debug"
    echo "  $0 --keep                    # Keep Docker running for debugging"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_usage
            exit 0
            ;;
        -k|--keep)
            KEEP_RUNNING=true
            shift
            ;;
        -s|--skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -p|--pattern)
            TEST_PATTERN="$2"
            shift 2
            ;;
        -d|--debug)
            DEBUG=true
            PYTEST_ARGS="$PYTEST_ARGS --log-cli-level=DEBUG"
            shift
            ;;
        -n|--no-coverage)
            RUN_COVERAGE=false
            shift
            ;;
        -c|--clean)
            CLEAN_FIRST=true
            shift
            ;;
        -v|--verbose)
            PYTEST_ARGS="$PYTEST_ARGS -vv"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        if [[ "$SKIP_DOCKER" == "false" ]]; then
            exit 1
        fi
        return 1
    fi
    
    if ! docker ps &> /dev/null; then
        log_error "Docker daemon is not running"
        if [[ "$SKIP_DOCKER" == "false" ]]; then
            exit 1
        fi
        return 1
    fi
    
    return 0
}

start_openfire() {
    log_info "Starting Openfire XMPP server..."
    
    # Check if container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${OPENFIRE_CONTAINER}$"; then
        if docker ps --format '{{.Names}}' | grep -q "^${OPENFIRE_CONTAINER}$"; then
            log_info "Openfire container already running"
            return 0
        else
            log_info "Starting existing Openfire container..."
            docker start "$OPENFIRE_CONTAINER"
        fi
    else
        log_info "Creating new Openfire container..."
        docker run -d \
            --name "$OPENFIRE_CONTAINER" \
            -p "${XMPP_PORT}:5222" \
            -p "${ADMIN_PORT}:9090" \
            -e DOMAIN=test.aztm \
            -e ADMIN_PASSWORD=admin123 \
            "$OPENFIRE_IMAGE"
    fi
    
    # Wait for Openfire to be ready
    log_info "Waiting for Openfire to be ready..."
    local max_wait=60
    local waited=0
    
    while [ $waited -lt $max_wait ]; do
        if nc -z localhost $XMPP_PORT 2>/dev/null; then
            log_success "Openfire is ready!"
            sleep 5  # Extra time for full initialization
            return 0
        fi
        echo -n "."
        sleep 2
        ((waited+=2))
    done
    
    echo ""
    log_error "Openfire failed to start within ${max_wait} seconds"
    return 1
}

stop_openfire() {
    if [[ "$KEEP_RUNNING" == "true" ]]; then
        log_info "Keeping Openfire running (--keep flag set)"
        log_info "Container: $OPENFIRE_CONTAINER"
        log_info "Admin UI: http://localhost:${ADMIN_PORT}"
        return
    fi
    
    log_info "Stopping Openfire container..."
    docker stop "$OPENFIRE_CONTAINER" 2>/dev/null || true
    
    if [[ "$CLEAN_FIRST" == "true" ]]; then
        log_info "Removing Openfire container..."
        docker rm "$OPENFIRE_CONTAINER" 2>/dev/null || true
    fi
}

cleanup() {
    local exit_code=$?
    log_info "Cleaning up..."
    
    if [[ "$SKIP_DOCKER" == "false" ]]; then
        stop_openfire
    fi
    
    # Kill any remaining test processes
    pkill -f "aztm.*test" 2>/dev/null || true
    
    exit $exit_code
}

run_tests() {
    local test_args=""
    local marker=""
    
    # Build test command based on type
    case $TEST_TYPE in
        unit)
            marker="-m 'mock or not integration'"
            test_args="tests/unit tests/regression/test_*connectivity.py::TestMockedConnectivity"
            ;;
        integration)
            if [[ "$SKIP_DOCKER" == "true" ]]; then
                log_warning "Skipping integration tests (--skip-docker set)"
                return 0
            fi
            marker="-m integration"
            test_args="tests/regression"
            ;;
        performance)
            marker="-m performance"
            test_args="tests/regression/test_performance.py tests/performance"
            ;;
        all)
            test_args="tests/"
            ;;
        *)
            log_error "Unknown test type: $TEST_TYPE"
            return 1
            ;;
    esac
    
    # Add pattern filter if specified
    if [[ -n "$TEST_PATTERN" ]]; then
        PYTEST_ARGS="$PYTEST_ARGS -k '$TEST_PATTERN'"
    fi
    
    # Add coverage if enabled
    if [[ "$RUN_COVERAGE" == "true" ]]; then
        PYTEST_ARGS="$PYTEST_ARGS --cov=aztm --cov-report=term-missing --cov-report=html"
    fi
    
    # Add timeout
    PYTEST_ARGS="$PYTEST_ARGS --timeout=$TEST_TIMEOUT"
    
    # Build final command
    local cmd="pytest $test_args $marker $PYTEST_ARGS"
    
    log_info "Running tests: $cmd"
    
    # Set environment variables
    export AZTM_HOST=localhost
    export AZTM_PORT=$XMPP_PORT
    export AZTM_DOMAIN=test.aztm
    export AZTM_LOG_LEVEL=$([[ "$DEBUG" == "true" ]] && echo "DEBUG" || echo "INFO")
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # Run tests
    cd "$PROJECT_ROOT"
    eval $cmd
}

generate_report() {
    if [[ "$RUN_COVERAGE" == "true" ]] && [[ -d "htmlcov" ]]; then
        log_info "Coverage report generated: file://$PROJECT_ROOT/htmlcov/index.html"
        
        # Try to open in browser on macOS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            open "htmlcov/index.html" 2>/dev/null || true
        fi
    fi
    
    # Check for test results
    if [[ -f "junit.xml" ]]; then
        log_info "JUnit report available: $PROJECT_ROOT/junit.xml"
    fi
}

# Main execution
main() {
    log_info "AZTM Regression Test Runner"
    log_info "Project root: $PROJECT_ROOT"
    
    # Set up trap for cleanup
    trap cleanup EXIT INT TERM
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Check Python environment
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    # Check if aztm package is installed
    if ! python3 -c "import aztm" 2>/dev/null; then
        log_warning "aztm package not installed, installing in development mode..."
        pip install -e ".[dev]"
    fi
    
    # Clean if requested
    if [[ "$CLEAN_FIRST" == "true" ]] && check_docker; then
        log_info "Cleaning up old containers..."
        docker stop "$OPENFIRE_CONTAINER" 2>/dev/null || true
        docker rm "$OPENFIRE_CONTAINER" 2>/dev/null || true
    fi
    
    # Start Docker services if needed
    if [[ "$SKIP_DOCKER" == "false" ]] && [[ "$TEST_TYPE" != "unit" ]]; then
        if check_docker; then
            if ! start_openfire; then
                log_error "Failed to start Openfire"
                exit 1
            fi
        else
            log_warning "Docker not available, skipping integration tests"
            SKIP_DOCKER=true
        fi
    fi
    
    # Run the tests
    log_info "Starting test execution..."
    if run_tests; then
        log_success "All tests passed!"
        generate_report
        exit 0
    else
        log_error "Some tests failed"
        generate_report
        exit 1
    fi
}

# Run main function
main