import SwiftUI

struct CheckView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                PanelCard(title: "Run Check", subtitle: "Use the Python backend already in this repo.") {
                    VStack(alignment: .leading, spacing: 14) {
                        dropZone

                        HStack(alignment: .center, spacing: 14) {
                            Stepper(value: $model.quantity, in: 1...10_000) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Quantity")
                                        .font(.subheadline)
                                    Text("\(model.quantity)")
                                        .font(.title3.weight(.semibold))
                                }
                            }
                            .frame(maxWidth: 220, alignment: .leading)

                            Spacer()

                            Button("Choose File") {
                                model.pickStepFile()
                            }
                            .buttonStyle(.bordered)

                            Button {
                                Task {
                                    await model.analyzeSelectedFile()
                                }
                            } label: {
                                if model.isAnalyzing {
                                    ProgressView()
                                        .controlSize(.small)
                                } else {
                                    Text("Run Analysis")
                                }
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(model.selectedFileURL == nil || !model.hasAnalysisRuntime || model.isAnalyzing)
                        }

                        if let selectedFileURL = model.selectedFileURL {
                            Text(selectedFileURL.path)
                                .font(.footnote.monospaced())
                                .foregroundStyle(AppTheme.mutedText)
                                .textSelection(.enabled)
                        }

                        if !model.hasAnalysisRuntime {
                            Text("Analysis runtime is not currently available. Check Diagnostics to confirm the selected Python environment can import OCC.")
                                .font(.subheadline)
                                .foregroundStyle(AppTheme.warning)
                        }
                    }
                }

                if let analysis = model.analysis {
                    summarySection(analysis)
                    processSection(analysis.processData)
                    rulesSection(analysis.rules)
                } else {
                    ContentUnavailableView(
                        "No Analysis Yet",
                        systemImage: "cube.transparent",
                        description: Text("Choose a STEP file, set the quantity, and run the backend check.")
                    )
                    .frame(maxWidth: .infinity)
                    .padding(.top, 28)
                }
            }
            .padding(24)
        }
    }

    private var dropZone: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("STEP File")
                .font(.subheadline.weight(.medium))

            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Color.clear)
                .strokeBorder(style: StrokeStyle(lineWidth: 1.25, dash: [8, 8]))
                .foregroundStyle(AppTheme.panelBorder)
                .frame(height: 140)
                .overlay {
                    VStack(spacing: 10) {
                        Image(systemName: "square.and.arrow.down.on.square")
                            .font(.system(size: 28, weight: .medium))
                            .foregroundStyle(AppTheme.accentColor)
                        Text("Drop a .step or .stp file here")
                            .font(.headline)
                        Text("or use the file picker")
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.mutedText)
                    }
                }
                .dropDestination(for: URL.self) { items, _ in
                    guard let url = items.first else {
                        return false
                    }
                    model.acceptDroppedFile(url)
                    return true
                }
        }
    }

    private func summarySection(_ analysis: AnalysisResponse) -> some View {
        HStack(alignment: .top, spacing: 18) {
            PanelCard(title: "Summary") {
                VStack(alignment: .leading, spacing: 10) {
                    Label(
                        analysis.summary.passed ? "All active rules passed" : "\(analysis.summary.failedRuleCount) rule(s) failed",
                        systemImage: analysis.summary.passed ? "checkmark.circle.fill" : "xmark.octagon.fill"
                    )
                    .foregroundStyle(analysis.summary.passed ? AppTheme.success : AppTheme.failure)
                    keyValueRow("File", analysis.filePath)
                    keyValueRow("Rule Multiplier", formatMultiplier(analysis.summary.ruleMultiplier))
                }
            }

            PanelCard(title: "Costs") {
                VStack(alignment: .leading, spacing: 10) {
                    keyValueRow("Unit Estimate", formatCurrency(analysis.processData.totalEstimatedCostEur))
                    keyValueRow("Batch Estimate", formatCurrency(analysis.processData.batchTotalEstimatedCostEur))
                    keyValueRow("Machine Type", analysis.processData.machineType)
                }
            }
        }
    }

    private func processSection(_ processData: PartProcessDataPayload) -> some View {
        PanelCard(title: "Part Facts", subtitle: processData.materialLabel) {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                keyValueRow("Part BBox", "\(format(processData.partBBoxXMm)) x \(format(processData.partBBoxYMm)) x \(format(processData.partBBoxZMm)) mm")
                keyValueRow("Stock BBox", "\(format(processData.stockBBoxXMm)) x \(format(processData.stockBBoxYMm)) x \(format(processData.stockBBoxZMm)) mm")
                keyValueRow("Volume", "\(format(processData.volumeMm3)) mm³")
                keyValueRow("Removed Volume", "\(format(processData.removedVolumeMm3)) mm³")
                keyValueRow("Mass", "\(format(processData.massKg)) kg")
                keyValueRow("Surface Complexity", "\(processData.surfaceComplexityFaces) faces")
                keyValueRow("Setups", processData.requiredSetupDirections)
                keyValueRow("Estimated Roughing MRR", "\(format(processData.estimatedRoughingMrrMm3PerMin)) mm³/min")
            }
        }
    }

    private func rulesSection(_ rules: [RulePayload]) -> some View {
        PanelCard(title: "Rule Results", subtitle: "\(rules.count) evaluated") {
            VStack(spacing: 12) {
                ForEach(rules) { rule in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 10) {
                            Circle()
                                .fill(rule.passed ? AppTheme.success : AppTheme.failure)
                                .frame(width: 10, height: 10)
                            Text(rule.name)
                                .font(.headline)
                            Spacer()
                            Text(rule.passed ? "PASS" : "FAIL")
                                .font(.caption.weight(.bold))
                                .foregroundStyle(rule.passed ? AppTheme.success : AppTheme.failure)
                        }

                        Text(rule.summary)
                            .font(.subheadline)
                        Text(rule.details)
                            .font(.footnote)
                            .foregroundStyle(AppTheme.mutedText)

                        HStack(spacing: 18) {
                            smallStat("Detected", "\(rule.detectedFeatures)")
                            smallStat("Pass", "\(rule.passedFeatures)")
                            smallStat("Fail", "\(rule.failedFeatures)")
                            smallStat("Multiplier", formatMultiplier(rule.ruleMultiplier))
                        }
                    }
                    .padding(.bottom, 12)

                    if rule.id != rules.last?.id {
                        Divider()
                    }
                }
            }
        }
    }

    private func smallStat(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.caption2.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)
            Text(value)
                .font(.subheadline.weight(.semibold))
        }
    }

    private func keyValueRow(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.caption2.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)
            Text(value)
                .font(.subheadline)
                .textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func format(_ value: Double) -> String {
        value.formatted(.number.precision(.fractionLength(2)))
    }

    private func formatCurrency(_ value: Double) -> String {
        value.formatted(.currency(code: "EUR"))
    }

    private func formatMultiplier(_ value: Double) -> String {
        "\(format(value))x"
    }
}
