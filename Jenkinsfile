// ─────────────────────────────────────────────────────────────────────────────
// Playwright Test Pipeline with AI Healer  (Windows Jenkins)
//
// Stages:
//   1. Checkout
//   2. Setup  – install Node deps + Playwright browsers + Python deps
//   3. Test   – run Playwright and capture JSON report
//   4. Heal   – invoke Python healer agent directly (playwright-test-healer)
//              which runs/debugs/fixes/verifies via MCP tools
//   5. Commit – push healed test files to a dedicated branch
//
// Jenkins agent requirement:
//   GitHub Copilot CLI must be installed and already signed in on the agent.
//
// Pipeline parameters (set in Jenkins UI or trigger payload):
//   DRY_RUN      – analyse failures but do NOT write fixes (default: false)
//   SKIP_HEALING – bypass the Heal stage entirely            (default: false)
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
            description: 'Skip the Heal stage (useful for baseline runs)'
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
        HEAL_EXIT_CODE         = '0'
        COPILOT_TIMEOUT        = '300'
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
                        if exist allure-results rd /s /q allure-results
                        if exist allure-report rd /s /q allure-report
                        if exist test-results rd /s /q test-results
                        mkdir reports
                        mkdir published-reports
                        mkdir allure-results
                        mkdir allure-report
                        mkdir test-results
                    '''

                    def grepFlag = params.TEST_GREP
                        ? "--grep \"${params.TEST_GREP}\""
                        : ''

                    def exitCode = bat(
                        returnStatus: true,
                        script: "set \"PLAYWRIGHT_HTML_OUTPUT_DIR=playwright-report/original-execution\" && set \"ALLURE_RESULTS_DIR=allure-results/original-execution\" && npx playwright test ${grepFlag}"
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
                        & './scripts/generate-jenkins-report.ps1' -OutputDir 'published-reports/original-execution' -Title 'Original Execution - Playwright Report' -JsonReportPath 'test-results/results.json' -ReportLink '../../playwright-report/original-execution/index.html'
                    '''
                    archiveArtifacts artifacts: 'playwright-report/original-execution/**/*', allowEmptyArchive: true
                    archiveArtifacts artifacts: 'allure-results/original-execution/**/*', allowEmptyArchive: true
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
                    // Ensure branch exists and is checked out BEFORE healing (code changes)
                    bat '''
                        git rev-parse --verify main >nul 2>nul
                        if %ERRORLEVEL% NEQ 0 (
                            git checkout -b main
                        ) else (
                            git checkout main
                        )
                    '''
                    def dryRun  = params.DRY_RUN ? '--dry-run' : ''
                    def healExitCode = bat(
                        returnStatus: true,
                        script: "set \"PYTHONIOENCODING=utf-8\" && python ${env.HEALER_SCRIPT} --report ${env.PLAYWRIGHT_JSON_REPORT} --workspace . --output ${env.HEALING_REPORT} --copilot-timeout ${env.COPILOT_TIMEOUT} ${dryRun}"
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

        // ── 5. Commit healed files ───────────────────────────────────────────
        stage('Commit fixes') {
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
                    def newBranch = "healed-fixes-${env.BUILD_NUMBER}"

                    def hasChanges = bat(
                        returnStatus: true,
                        script: 'git status --porcelain -- "*.ts" ":!*.bak_*" | findstr .'
                    )

                    if (hasChanges != 0) {
                        echo 'No healed test file changes to commit.'
                        return
                    }

                    bat """
                        git checkout -b ${newBranch}
                        git add "*.ts" ":!*.bak_*"
                        git diff --cached --quiet && echo "Nothing to commit." || git commit -m "fix: auto-heal failing Playwright tests [skip ci]"
                    """

                    def hasPush = bat(returnStatus: true, script: 'git remote | findstr origin')
                    if (hasPush == 0) {
                        bat "git push origin ${newBranch}"
                        echo "Healed changes pushed to branch: ${newBranch}"
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
            archiveArtifacts artifacts: 'allure-results/**/*', allowEmptyArchive: true

            script {
                def healedAllFailures = (env.INITIAL_EXIT_CODE != '0' && env.HEAL_EXIT_CODE == '0' && !params.DRY_RUN)

                def allureResults = []
                if (fileExists('allure-results/original-execution')) {
                    allureResults << [path: 'allure-results/original-execution']
                }
                if (allureResults && !healedAllFailures) {
                    allure([
                        includeProperties: false,
                        jdk: '',
                        properties: [],
                        reportBuildPolicy: 'ALWAYS',
                        results: allureResults
                    ])
                } else if (allureResults && healedAllFailures) {
                    echo 'Skipping Allure publisher to keep build SUCCESS after successful healing of initial failures.'
                }

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

                // Healer exit 1 means some tests could not be fixed
                if (env.HEAL_EXIT_CODE == '1') {
                    currentBuild.result = 'UNSTABLE'
                }

                if (env.INITIAL_EXIT_CODE != '0' && env.HEAL_EXIT_CODE == '2') {
                    currentBuild.result = 'FAILURE'
                    error 'Tests failed and the healer could not run because GitHub Copilot CLI is unavailable for the Jenkins account.'
                }

                if (env.INITIAL_EXIT_CODE != '0' && params.SKIP_HEALING) {
                    currentBuild.result = 'FAILURE'
                    error 'Tests failed and SKIP_HEALING=true — no healing attempted.'
                }

                // If tests initially failed but healer fully fixed them, keep final build green.
                if (healedAllFailures) {
                    currentBuild.result = 'SUCCESS'
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
