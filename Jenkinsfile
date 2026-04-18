// ─────────────────────────────────────────────────────────────────────────────
// Playwright Test Pipeline with AI Healer
//
// Stages:
//   1. Checkout
//   2. Setup  – install Node deps + Playwright browsers + Python deps
//   3. Test   – run Playwright and capture JSON report
//   4. Heal   – invoke Python healer agent on failures (Claude AI)
//   5. Re-run – verify fixes by re-running the full suite
//   6. Commit – push healed test files back to the branch
//
// Required Jenkins credentials:
//   anthropic-api-key  – Secret text credential with your Anthropic API key
//
// Pipeline parameters (set in Jenkins UI or trigger payload):
//   DRY_RUN      – analyse failures but do NOT write fixes (default: false)
//   SKIP_HEALING – bypass the Heal + Re-run stages entirely  (default: false)
//   TEST_GREP    – optional grep filter, e.g. "search"       (default: "")
// ─────────────────────────────────────────────────────────────────────────────

pipeline {
    agent any

    parameters {
        booleanParam(
            name: 'DRY_RUN',
            defaultValue: false,
            description: 'Analyse failures but do not write fixes to disk'
        )
        booleanParam(
            name: 'SKIP_HEALING',
            defaultValue: false,
            description: 'Skip the Heal and Re-run stages (useful for baseline runs)'
        )
        string(
            name: 'TEST_GREP',
            defaultValue: '',
            description: 'Optional: grep filter for test titles, e.g. "search"'
        )
    }

    environment {
        // Injected from Jenkins credential store
        ANTHROPIC_API_KEY = credentials('anthropic-api-key')

        // Paths used across stages
        PLAYWRIGHT_JSON_REPORT = 'test-results/results.json'
        HEALING_REPORT         = 'test-results/healing_report.json'
        HEALER_SCRIPT          = 'healer/healer_agent.py'
        HEALER_LOG             = 'healer.log'

        // Application URL — override per environment if needed
        BASE_URL = "${env.BASE_URL ?: 'http://localhost:5173'}"
    }

    options {
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    stages {

        // ── 1. Checkout ──────────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // ── 2. Setup ─────────────────────────────────────────────────────────
        stage('Setup') {
            parallel {
                stage('Node / Playwright') {
                    steps {
                        sh 'node --version && npm --version'
                        sh 'npm ci'
                        sh 'npx playwright install --with-deps chromium'
                    }
                }
                stage('Python') {
                    steps {
                        sh 'python3 --version && pip3 --version'
                        sh 'pip3 install --quiet -r healer/requirements.txt'
                    }
                }
            }
        }

        // ── 3. Test ──────────────────────────────────────────────────────────
        stage('Test') {
            steps {
                script {
                    // Ensure the output directory exists
                    sh 'mkdir -p test-results'

                    def grepFlag = params.TEST_GREP
                        ? "--grep \"${params.TEST_GREP}\""
                        : ''

                    // Run with both HTML (for humans) and JSON (for healer)
                    // returnStatus=true so Jenkins doesn't abort on test failure
                    def exitCode = sh(
                        returnStatus: true,
                        script: """
                            npx playwright test \
                                --reporter=html,json \
                                --output=${env.PLAYWRIGHT_JSON_REPORT} \
                                ${grepFlag}
                        """
                    )

                    env.INITIAL_EXIT_CODE = exitCode.toString()

                    if (exitCode == 0) {
                        echo 'All tests passed — no healing needed.'
                    } else {
                        echo "Tests finished with exit code ${exitCode}. Healer will process failures."
                    }
                }
            }
            post {
                always {
                    // Publish HTML report regardless of outcome
                    publishHTML(target: [
                        allowMissing:         true,
                        alwaysLinkToLastBuild: true,
                        keepAll:              true,
                        reportDir:            'playwright-report',
                        reportFiles:          'index.html',
                        reportName:           'Playwright Report (initial run)'
                    ])
                }
            }
        }

        // ── 4. Heal ──────────────────────────────────────────────────────────
        stage('Heal') {
            when {
                allOf {
                    // Only run when there are failures
                    expression { env.INITIAL_EXIT_CODE != '0' }
                    expression { !params.SKIP_HEALING }
                    // JSON report must exist
                    expression { fileExists(env.PLAYWRIGHT_JSON_REPORT) }
                }
            }
            steps {
                script {
                    def dryRun = params.DRY_RUN ? '--dry-run' : ''

                    def healExitCode = sh(
                        returnStatus: true,
                        script: """
                            python3 ${env.HEALER_SCRIPT} \
                                --report  ${env.PLAYWRIGHT_JSON_REPORT} \
                                --workspace . \
                                --output  ${env.HEALING_REPORT} \
                                ${dryRun}
                        """
                    )

                    // 0 = all healed, 1 = some unhealed, 2 = startup error
                    env.HEAL_EXIT_CODE = healExitCode.toString()

                    if (healExitCode == 0) {
                        echo 'Healer: all failures addressed.'
                    } else if (healExitCode == 1) {
                        echo 'Healer: some failures could not be auto-fixed (see healing_report.json).'
                    } else {
                        error "Healer exited with unexpected code ${healExitCode} — check healer.log."
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: "${env.HEALING_REPORT},${env.HEALER_LOG}", allowEmptyArchive: true
                }
            }
        }

        // ── 5. Re-run ────────────────────────────────────────────────────────
        stage('Re-run after healing') {
            when {
                allOf {
                    expression { env.INITIAL_EXIT_CODE != '0' }
                    expression { !params.SKIP_HEALING }
                    expression { !params.DRY_RUN }
                    // Only re-run when at least one fix was applied (exit 0)
                    expression { env.HEAL_EXIT_CODE == '0' }
                }
            }
            steps {
                script {
                    def grepFlag = params.TEST_GREP
                        ? "--grep \"${params.TEST_GREP}\""
                        : ''

                    def exitCode = sh(
                        returnStatus: true,
                        script: """
                            npx playwright test \
                                --reporter=html,json \
                                --output=test-results/rerun-results.json \
                                ${grepFlag}
                        """
                    )

                    env.RERUN_EXIT_CODE = exitCode.toString()

                    if (exitCode == 0) {
                        echo 'Re-run passed — healer successfully fixed all tests!'
                    } else {
                        // Do not error here; let post-pipeline logic decide
                        echo "Re-run still has failures (exit ${exitCode}). Manual review required."
                    }
                }
            }
            post {
                always {
                    publishHTML(target: [
                        allowMissing:         true,
                        alwaysLinkToLastBuild: true,
                        keepAll:              true,
                        reportDir:            'playwright-report',
                        reportFiles:          'index.html',
                        reportName:           'Playwright Report (after healing)'
                    ])
                }
            }
        }

        // ── 6. Commit healed files ───────────────────────────────────────────
        stage('Commit fixes') {
            when {
                allOf {
                    expression { env.RERUN_EXIT_CODE == '0' }
                    expression { !params.DRY_RUN }
                }
            }
            steps {
                script {
                    sh '''
                        git config user.email "healer-bot@ci.local"
                        git config user.name  "Healer Bot"
                        git add --all
                        git diff --cached --quiet \
                            && echo "Nothing to commit — tests were already correct." \
                            || git commit -m "fix: auto-heal failing Playwright tests [skip ci]"
                    '''

                    // Push only if a remote is configured
                    def hasPush = sh(returnStatus: true, script: 'git remote | grep -q origin')
                    if (hasPush == 0) {
                        sh 'git push origin HEAD'
                    } else {
                        echo 'No remote "origin" found — skipping push.'
                    }
                }
            }
        }

    } // end stages

    // ── Post-pipeline ─────────────────────────────────────────────────────────
    post {
        always {
            archiveArtifacts artifacts: 'test-results/**', allowEmptyArchive: true

            script {
                // Annotate build description with healing outcome
                if (fileExists(env.HEALING_REPORT)) {
                    def hr = readJSON file: env.HEALING_REPORT
                    currentBuild.description = [
                        "Failures: ${hr.total_failures}",
                        "Healed: ${hr.healed}",
                        "Unhealed: ${hr.failed_to_heal}",
                        params.DRY_RUN ? '[DRY-RUN]' : ''
                    ].findAll { it }.join(' | ')
                }

                // Fail the build if re-run still has failures
                if (env.RERUN_EXIT_CODE && env.RERUN_EXIT_CODE != '0') {
                    currentBuild.result = 'FAILURE'
                    error 'Tests still failing after healing — manual fix required.'
                }

                // Fail if initial tests failed and healing was skipped
                if (env.INITIAL_EXIT_CODE != '0' && params.SKIP_HEALING) {
                    currentBuild.result = 'FAILURE'
                    error 'Tests failed and SKIP_HEALING=true — no healing attempted.'
                }
            }
        }

        success {
            echo 'Pipeline completed successfully.'
        }

        failure {
            echo 'Pipeline failed. Check the Playwright reports and healing_report.json for details.'
        }
    }
}
