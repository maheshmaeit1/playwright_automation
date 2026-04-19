// ─────────────────────────────────────────────────────────────────────────────
// Playwright Test Pipeline with AI Healer  (Windows Jenkins)
//
// Stages:
//   1. Checkout
//   2. Setup  – install Node deps + Playwright browsers + Python deps
//   3. Test   – run Playwright and capture JSON report
//   4. Heal   – invoke Python healer agent on failures (GitHub Copilot CLI)
//   5. Re-run – verify fixes by re-running the full suite
//   6. Commit – push healed test files back to the branch
//
// Jenkins agent requirement:
//   GitHub Copilot CLI must be installed and already signed in on the agent.
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
        // Paths used across stages
        PLAYWRIGHT_JSON_REPORT = 'test-results/results.json'
        HEALING_REPORT         = 'test-results/healing_report.json'
        HEALER_SCRIPT          = 'healer/healer_agent.py'
        HEALER_LOG             = 'healer.log'
        PATH                   = "${env.PATH};C:/Users/mahes/AppData/Roaming/Code/User/globalStorage/github.copilot-chat/copilotCli"

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
                        bat 'node --version && npm --version'
                        bat '''
                            where copilot >nul 2>nul
                            if %ERRORLEVEL% EQU 0 (
                                copilot --version
                            ) else (
                                echo Copilot CLI is not on PATH for this Jenkins account.
                                echo The Python healer will try its own fallback discovery.
                            )
                        '''
                        bat 'npm i'
                        bat 'npx playwright install chromium'
                    }
                }
                stage('Python') {
                    steps {
                        bat 'python --version && python -m pip --version'
                        bat 'python -m pip install --quiet -r healer/requirements.txt'
                    }
                }
            }
        }

        // ── 3. Test ──────────────────────────────────────────────────────────
        stage('Test') {
            steps {
                script {
                    bat '''
                        if exist reports rd /s /q reports
                        if exist published-reports rd /s /q published-reports
                        if exist playwright-report rd /s /q playwright-report
                        if exist test-results rd /s /q test-results
                        mkdir reports
                        mkdir published-reports
                        mkdir test-results
                    '''

                    def grepFlag = params.TEST_GREP
                        ? "--grep \"${params.TEST_GREP}\""
                        : ''

                    def exitCode = bat(
                        returnStatus: true,
                        script: "set \"PLAYWRIGHT_HTML_OUTPUT_DIR=reports/original-execution/playwright\" && npx playwright test ${grepFlag}"
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
                    powershell '''
                        & './scripts/generate-jenkins-report.ps1' -OutputDir 'published-reports/original-execution' -Title 'Original Execution - Playwright Report' -JsonReportPath 'test-results/results.json'
                    '''
                    archiveArtifacts artifacts: 'reports/original-execution/playwright/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'published-reports/original-execution/**/*', allowEmptyArchive: true
                    publishHTML(target: [
                        allowMissing:          true,
                        alwaysLinkToLastBuild: true,
                        keepAll:               true,
                        reportDir:             'published-reports/original-execution',
                        reportFiles:           'index.html',
                        reportName:            'Original Execution - Playwright Report'
                    ])
                }
            }
        }

        // ── 4. Heal ──────────────────────────────────────────────────────────
        stage('Heal') {
            when {
                allOf {
                    expression { env.INITIAL_EXIT_CODE != '0' }
                    expression { !params.SKIP_HEALING }
                    expression { fileExists(env.PLAYWRIGHT_JSON_REPORT) }
                }
            }
            steps {
                script {
                    def dryRun = params.DRY_RUN ? '--dry-run' : ''

                    def healExitCode = bat(
                        returnStatus: true,
                        script: "set \"PYTHONIOENCODING=utf-8\" && python ${env.HEALER_SCRIPT} --report ${env.PLAYWRIGHT_JSON_REPORT} --workspace . --output ${env.HEALING_REPORT} ${dryRun}"
                    )

                    env.HEAL_EXIT_CODE = healExitCode.toString()

                    if (healExitCode == 0) {
                        echo 'Healer: all failures addressed.'
                    } else if (healExitCode == 1) {
                        echo 'Healer: some failures could not be auto-fixed (see healing_report.json).'
                    } else if (healExitCode == 2) {
                        echo 'Healer unavailable: Copilot CLI is not installed or not signed in for the Jenkins account. Skipping self-healing for this run.'
                    } else {
                        error "Healer exited with unexpected code ${healExitCode} — check healer.log."
                    }
                }
            }
            post {
                always {
                    powershell '''
                        & './scripts/generate-jenkins-report.ps1' -OutputDir 'published-reports/heal' -Title 'Test Heal Report' -SourceHtmlPath 'test-results/healing_report.html' -FallbackMessage 'No healing HTML report was generated for this run.'
                    '''
                    archiveArtifacts artifacts: 'published-reports/heal/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: "${env.HEALING_REPORT}", allowEmptyArchive: true
                    archiveArtifacts artifacts: "${env.HEALER_LOG}", allowEmptyArchive: true
                    publishHTML(target: [
                        allowMissing:          true,
                        alwaysLinkToLastBuild: true,
                        keepAll:               true,
                        reportDir:             'published-reports/heal',
                        reportFiles:           'index.html',
                        reportName:            'Test Heal Report'
                    ])
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
                    expression { env.HEAL_EXIT_CODE == '0' }
                }
            }
            steps {
                script {
                    def grepFlag = params.TEST_GREP
                        ? "--grep \"${params.TEST_GREP}\""
                        : ''

                    def exitCode = bat(
                        returnStatus: true,
                        script: "set \"PLAYWRIGHT_HTML_OUTPUT_DIR=reports/re-execution/playwright\" && npx playwright test ${grepFlag}"
                    )

                    if (fileExists('test-results/results.json')) {
                        powershell "Copy-Item 'test-results/results.json' 'test-results/rerun-results.json' -Force"
                    }

                    env.RERUN_EXIT_CODE = exitCode.toString()

                    if (exitCode == 0) {
                        echo 'Re-run passed — healer successfully fixed all tests!'
                    } else {
                        echo "Re-run still has failures (exit ${exitCode}). Manual review required."
                    }
                }
            }
            post {
                always {
                    powershell '''
                        & './scripts/generate-jenkins-report.ps1' -OutputDir 'published-reports/re-execution' -Title 'Re-execution - Playwright Report' -JsonReportPath 'test-results/rerun-results.json'
                    '''
                    archiveArtifacts artifacts: 'reports/re-execution/playwright/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'published-reports/re-execution/**/*', allowEmptyArchive: true
                    publishHTML(target: [
                        allowMissing:          true,
                        alwaysLinkToLastBuild: true,
                        keepAll:               true,
                        reportDir:             'published-reports/re-execution',
                        reportFiles:           'index.html',
                        reportName:            'Re-execution - Playwright Report'
                    ])
                }
            }
        }

        // ── 6. Commit healed files ───────────────────────────────────────────
        stage('Commit fixes') {
            when {
                expression { false } // disabled
            }
            steps {
                script {
                    bat """
                        git config user.email "healer-bot@ci.local"
                        git config user.name "Healer Bot"
                        git add --all
                        git diff --cached --quiet && echo "Nothing to commit." || git commit -m "fix: auto-heal failing Playwright tests [skip ci]"
                    """

                    def hasPush = bat(returnStatus: true, script: 'git remote | findstr origin')
                    if (hasPush == 0) {
                        bat 'git push origin HEAD'
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
            archiveArtifacts artifacts: 'test-results/**/*', allowEmptyArchive: true
            archiveArtifacts artifacts: 'playwright-report/**/*', allowEmptyArchive: true

            script {
                if (fileExists(env.HEALING_REPORT)) {
                    def healingReportText = readFile(file: env.HEALING_REPORT).trim()
                    if (healingReportText) {
                        def hr = new groovy.json.JsonSlurperClassic().parseText(healingReportText)
                        currentBuild.description = [
                            "Failures: ${hr.total_failures}",
                            "Healed: ${hr.healed}",
                            "Unhealed: ${hr.failed_to_heal}",
                            params.DRY_RUN ? '[DRY-RUN]' : ''
                        ].findAll { it }.join(' | ')
                    }
                }

                if (env.RERUN_EXIT_CODE && env.RERUN_EXIT_CODE != '0') {
                    currentBuild.result = 'FAILURE'
                    error 'Tests still failing after healing — manual fix required.'
                }

                if (env.INITIAL_EXIT_CODE != '0' && env.HEAL_EXIT_CODE == '2') {
                    currentBuild.result = 'FAILURE'
                    error 'Tests failed and the healer could not run because GitHub Copilot CLI is unavailable for the Jenkins account.'
                }

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
