import SwiftUI

enum AnalysisScreenMode {
    case recommendations
    case ruleResults
    case summary

    var emptyTitle: String {
        switch self {
        case .recommendations:
            return "No Recommendations Yet"
        case .ruleResults:
            return "No Rule Results Yet"
        case .summary:
            return "No Analysis Summary Yet"
        }
    }
}

struct CheckView: View {
    @ObservedObject var model: AppModel
    let mode: AnalysisScreenMode

    var body: some View {
        GeometryReader { geometry in
            let isCompactLayout = geometry.size.width < 1_140

            Group {
                if let analysis = model.analysis {
                    analysisLayout(
                        analysis,
                        availableWidth: geometry.size.width,
                        compact: isCompactLayout
                    )
                } else {
                    emptyStateLayout(compact: isCompactLayout)
                }
            }
        }
        .padding(24)
    }

    private func analysisLayout(_ analysis: AnalysisResponse, availableWidth: CGFloat, compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            backgroundRunBanner

            if compact {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        previewPanel
                        mainContent(analysis)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                HStack(alignment: .top, spacing: 24) {
                    ScrollView {
                        mainContent(analysis)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(
                        minWidth: contentColumnMinWidth(for: mode),
                        idealWidth: contentColumnIdealWidth(for: mode, totalWidth: availableWidth),
                        maxWidth: .infinity,
                        maxHeight: .infinity,
                        alignment: .topLeading
                    )

                    previewColumn(width: previewColumnWidth(for: mode, totalWidth: availableWidth))
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private func emptyStateLayout(compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            backgroundRunBanner

            if compact {
                previewPanel
                emptyStateCard
            } else {
                HStack(alignment: .top, spacing: 24) {
                    emptyStateCard
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                    previewColumn(width: previewColumnWidth(for: mode, totalWidth: 1_260))
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private func mainContent(_ analysis: AnalysisResponse) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            switch mode {
            case .recommendations:
                recommendationsSection(analysis.recommendations)
            case .ruleResults:
                rulesSection(analysis.rules)
            case .summary:
                summaryScreen(analysis)
            }
        }
    }

    private func previewColumn(width: CGFloat) -> some View {
        previewPanel
            .frame(width: width, alignment: .topLeading)
            .padding(.top, 4)
    }

    private func previewColumnWidth(for mode: AnalysisScreenMode, totalWidth: CGFloat) -> CGFloat {
        let clampedWidth = max(totalWidth, 1_140)
        switch mode {
        case .recommendations:
            return min(max(clampedWidth * 0.46, 520), 700)
        case .ruleResults:
            return min(max(clampedWidth * 0.44, 500), 660)
        case .summary:
            return min(max(clampedWidth * 0.42, 480), 620)
        }
    }

    private func contentColumnMinWidth(for mode: AnalysisScreenMode) -> CGFloat {
        switch mode {
        case .recommendations:
            return 360
        case .ruleResults:
            return 390
        case .summary:
            return 460
        }
    }

    private func contentColumnIdealWidth(for mode: AnalysisScreenMode, totalWidth: CGFloat) -> CGFloat {
        let previewWidth = previewColumnWidth(for: mode, totalWidth: totalWidth)
        let remaining = totalWidth - previewWidth - 24
        return max(contentColumnMinWidth(for: mode), remaining)
    }

    private var emptyStateCard: some View {
        PanelCard(title: mode.emptyTitle, subtitle: "Please load model to run analysis.") {
            ContentUnavailableView(
                "",
                systemImage: "cube.transparent",
                description: Text("Please load model to run analysis.")
            )
            .labelsHidden()
            .frame(maxWidth: .infinity, minHeight: 240)
        }
    }

    @ViewBuilder
    private var backgroundRunBanner: some View {
        if model.isRunningNextAnalysis, let pendingAnalysisFileName = model.pendingAnalysisFileName {
            PanelCard(title: "Running New Analysis", subtitle: "The current results stay visible until the next run finishes.") {
                HStack(spacing: 12) {
                    ProgressView()
                    VStack(alignment: .leading, spacing: 2) {
                        Text(pendingAnalysisFileName)
                            .font(.subheadline.weight(.semibold))
                        Text("Loading next analysis in the background")
                            .font(.caption)
                            .foregroundStyle(AppTheme.mutedText)
                    }
                    Spacer(minLength: 0)
                }
            }
        }
    }

    @ViewBuilder
    private var previewPanel: some View {
        if let previewFileURL = model.previewFileURL {
            PartPreview3DView(
                fileURL: previewFileURL,
                highlightedInsights: mode == .recommendations ? model.visibleFeatureInsights : [],
                focusedInsightID: mode == .recommendations ? model.focusedFeatureInsight?.id : nil
            )
        } else if model.isGeneratingPreview {
            PanelCard(title: "3D Preview", subtitle: "Analysis is ready. Generating preview mesh in the background.") {
                HStack(spacing: 12) {
                    ProgressView()
                    Text("Loading preview…")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.mutedText)
                }
                .frame(maxWidth: .infinity, minHeight: 120, alignment: .center)
            }
        } else {
            PanelCard(title: "3D Preview", subtitle: "Preview appears here after analysis.") {
                ContentUnavailableView(
                    "",
                    systemImage: "view.3d",
                    description: Text("Please load model to run analysis.")
                )
                .labelsHidden()
                .frame(maxWidth: .infinity, minHeight: 220)
            }
        }
    }

    private func summaryScreen(_ analysis: AnalysisResponse) -> some View {
        let processData = model.displayedProcessData ?? analysis.processData
        return VStack(alignment: .leading, spacing: 18) {
            overviewSection(analysis)
            factsSection(processData)
            preMultiplierDriversSection(processData)
            multiplierSection(processData)
            postMultiplierOutputsSection(processData)
            costsSection(processData)
        }
    }

    private func overviewSection(_ analysis: AnalysisResponse) -> some View {
        HStack(alignment: .top, spacing: 18) {
            PanelCard(title: "Overview") {
                VStack(alignment: .leading, spacing: 10) {
                    Label(
                        analysis.summary.passed ? "All active rules passed" : "\(analysis.summary.failedRuleCount) rule(s) failed",
                        systemImage: analysis.summary.passed ? "checkmark.circle.fill" : "xmark.octagon.fill"
                    )
                    .foregroundStyle(analysis.summary.passed ? AppTheme.success : AppTheme.failure)
                    keyValueRow("File", analysis.filePath)
                    keyValueRow("Rules Passed", "\(analysis.summary.passedRuleCount) / \(analysis.summary.totalRuleCount)")
                    keyValueRow("Rule Multiplier", formatMultiplier(analysis.summary.ruleMultiplier))
                }
            }

            PanelCard(title: "Current Top Recommendation") {
                VStack(alignment: .leading, spacing: 10) {
                    if let topRecommendation = analysis.recommendations.first {
                        recommendationBadge(topRecommendation.kind)
                        Text(topRecommendation.title)
                            .font(.headline)
                        Text(topRecommendation.summary)
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.mutedText)
                    } else {
                        Text("No recommendation available.")
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.mutedText)
                    }
                }
            }
        }
    }

    private func factsSection(_ processData: PartProcessDataPayload) -> some View {
        PanelCard(title: "Part Facts", subtitle: processData.materialLabel) {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                keyValueRow("Material", processData.materialLabel)
                keyValueRow("Machine Type", processData.machineType)
                keyValueRow("Part BBox", "\(format(processData.partBBoxXMm)) x \(format(processData.partBBoxYMm)) x \(format(processData.partBBoxZMm)) mm")
                keyValueRow("Stock BBox (+10/axis)", "\(format(processData.stockBBoxXMm)) x \(format(processData.stockBBoxYMm)) x \(format(processData.stockBBoxZMm)) mm")
                keyValueRow("Volume", "\(format(processData.volumeMm3)) mm³")
                keyValueRow("Stock Volume", "\(format(processData.stockVolumeMm3)) mm³")
                keyValueRow("Removed Volume", "\(format(processData.removedVolumeMm3)) mm³")
                keyValueRow("Part Surface Area", "\(format(processData.partSurfaceAreaMm2)) mm²")
                keyValueRow("Part SA/V", formatMetric(processData.partSavRatio))
                keyValueRow("BBox SA/V", formatMetric(processData.bboxSavRatio))
                keyValueRow("Mass", "\(format(processData.massKg)) kg")
                keyValueRow("Stock Mass", "\(format(processData.stockMassKg)) kg")
                keyValueRow("Setup Directions", processData.requiredSetupDirections)
                quantityControlRow
            }
        }
    }

    private var quantityControlRow: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("QUANTITY")
                .font(.caption2.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)

            HStack(spacing: 8) {
                Stepper(
                    value: Binding(
                        get: { model.quantity },
                        set: { model.setQuantity($0) }
                    ),
                    in: 1...100_000
                ) {
                    EmptyView()
                }
                .labelsHidden()
                .fixedSize()

                TextField(
                    "Qty",
                    value: Binding(
                        get: { model.quantity },
                        set: { model.setQuantity($0) }
                    ),
                    format: .number
                )
                .textFieldStyle(.roundedBorder)
                .frame(width: 92)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func preMultiplierDriversSection(_ processData: PartProcessDataPayload) -> some View {
        PanelCard(title: "Pre-Multiplier Drivers") {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                keyValueRow("Surface Area", formatMultiplier(processData.surfaceAreaRatio))
                keyValueRow("Surface Complexity", "\(processData.surfaceComplexityFaces) faces")
                keyValueRow("Hole Count", "\(processData.holeCount)")
                keyValueRow("Internal Radius Count", "\(processData.radiusCount)")
                keyValueRow("Machinability Index", formatMetric(processData.machinabilityIndex))
                keyValueRow("Baseline 6061 MRR", "\(format(processData.baseline6061MrrMm3PerMin)) mm³/min")
                keyValueRow("Estimated Roughing MRR", "\(format(processData.estimatedRoughingMrrMm3PerMin)) mm³/min")
                keyValueRow("Material Source", processData.materialBilletCostSource)
            }
        }
    }

    private func multiplierSection(_ processData: PartProcessDataPayload) -> some View {
        PanelCard(title: "Multipliers") {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                keyValueRow("Surface Area Multiplier", formatMultiplier(processData.surfaceAreaMultiplier))
                keyValueRow("Complexity Multiplier", formatMultiplier(processData.complexityMultiplier))
                keyValueRow("Hole Multiplier", formatMultiplier(processData.holeCountMultiplier))
                keyValueRow("Radius Multiplier", formatMultiplier(processData.radiusCountMultiplier))
                keyValueRow("Material Multiplier", formatMultiplier(processData.materialTimeMultiplier))
                keyValueRow("Rule Multiplier", formatMultiplier(processData.ruleMultiplier))
                keyValueRow("Total Time Multiplier", formatMultiplier(processData.totalTimeMultiplier))
                keyValueRow("Qty Multiplier", formatMultiplier(processData.qtyMultiplier))
            }
        }
    }

    private func postMultiplierOutputsSection(_ processData: PartProcessDataPayload) -> some View {
        PanelCard(title: "Post-Multiplier Outputs") {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                keyValueRow("Roughing Time (Pre Qty)", "\(format(processData.roughingTimeMin)) min")
                keyValueRow("Base Machining Time", "\(format(processData.baseMachiningTimeMin)) min")
                keyValueRow("Machining Time (Pre Qty)", "\(format(processData.machiningTimeMin)) min")
                keyValueRow("Machine Rate", formatCurrency(processData.machineHourlyRateEur))
            }
        }
    }

    private func costsSection(_ processData: PartProcessDataPayload) -> some View {
        PanelCard(title: "Costs") {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                keyValueRow("Raw Material Rate", "\(format(processData.materialBilletCostEurPerKg)) EUR/kg")
                keyValueRow("Material Base Fee", formatCurrency(processData.materialFixedCostEur))
                keyValueRow("Material Total", formatCurrency(processData.materialStockCostEur))
                keyValueRow("Roughing Cost", formatCurrency(processData.roughingCost))
                keyValueRow("Machining Cost", formatCurrency(processData.machiningCost))
                keyValueRow("Unit Estimate", formatCurrency(processData.totalEstimatedCostEur))
                keyValueRow("Batch Estimate", formatCurrency(processData.batchTotalEstimatedCostEur))
                keyValueRow("Material Fixed Cost Source", processData.materialFixedCostSource)
            }
        }
    }

    private func recommendationsSection(_ recommendations: [RecommendationPayload]) -> some View {
        PanelCard(
            title: "Recommendations",
            subtitle: recommendations.first?.kind == "blocker"
                ? "Fix blockers first, then reduce cost drivers. Click a recommendation to focus the geometry."
                : "Prioritized design guidance from the analysis. Click a recommendation to focus the geometry."
        ) {
            VStack(alignment: .leading, spacing: 14) {
                ForEach(recommendations) { recommendation in
                    let isSelected = model.selectedRecommendationID == recommendation.id

                    VStack(alignment: .leading, spacing: 10) {
                        HStack(alignment: .top, spacing: 10) {
                            recommendationBadge(recommendation.kind)

                            VStack(alignment: .leading, spacing: 4) {
                                Text(recommendation.title)
                                    .font(.headline)
                                Text(recommendation.summary)
                                    .font(.subheadline)
                            }

                            Spacer()

                            Text("P\(recommendation.priority)")
                                .font(.caption.monospacedDigit().weight(.semibold))
                                .foregroundStyle(AppTheme.mutedText)
                        }

                        Text(recommendation.impact)
                            .font(.footnote)
                            .foregroundStyle(AppTheme.mutedText)

                        if isSelected && !recommendation.featureGroups.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Where")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(AppTheme.accentColor)

                                ForEach(recommendation.featureGroups) { group in
                                    featureGroupRow(group)
                                }
                            }
                            .padding(.vertical, 4)
                        }

                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(recommendation.actions, id: \.self) { action in
                                HStack(alignment: .top, spacing: 8) {
                                    Text("-")
                                    Text(action)
                                }
                                .font(.footnote)
                            }
                        }

                        Text("Source: \(recommendation.source)")
                            .font(.caption)
                            .foregroundStyle(AppTheme.mutedText)
                    }
                    .padding(12)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(isSelected ? AppTheme.panelBackground.opacity(0.85) : Color.clear)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .stroke(isSelected ? AppTheme.accentColor.opacity(0.45) : AppTheme.panelBorder.opacity(0.4), lineWidth: 1)
                    )
                    .contentShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .onTapGesture {
                        model.selectRecommendation(recommendation)
                    }

                    if recommendation.id != recommendations.last?.id {
                        Divider()
                    }
                }
            }
        }
    }

    private func featureGroupRow(_ group: RecommendationFeatureGroup) -> some View {
        let isSelected = model.selectedFeatureGroupID == group.id
        let currentIndex = group.instances.firstIndex(where: { $0.id == model.selectedFeatureInstanceID }) ?? 0

        return VStack(alignment: .leading, spacing: 8) {
            Button {
                model.selectFeatureGroup(group)
            } label: {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: isSelected ? "scope" : "mappin.and.ellipse")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(isSelected ? AppTheme.accentColor : AppTheme.mutedText)

                    Text(group.count > 1 ? "x\(group.count) \(group.summary)" : group.summary)
                        .font(.footnote)
                        .multilineTextAlignment(.leading)

                    Spacer(minLength: 0)
                }
            }
            .buttonStyle(.plain)

            if isSelected, group.count > 1 {
                HStack(spacing: 10) {
                    Button {
                        model.stepSelectedFeatureInstance(in: group, delta: -1)
                    } label: {
                        Image(systemName: "chevron.left")
                    }
                    .buttonStyle(.bordered)

                    Text("\(currentIndex + 1) of \(group.count)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(AppTheme.mutedText)

                    Button {
                        model.stepSelectedFeatureInstance(in: group, delta: 1)
                    } label: {
                        Image(systemName: "chevron.right")
                    }
                    .buttonStyle(.bordered)

                    Spacer(minLength: 0)
                }
            }
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(isSelected ? AppTheme.accentColor.opacity(0.08) : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(isSelected ? AppTheme.accentColor.opacity(0.35) : AppTheme.panelBorder.opacity(0.3), lineWidth: 1)
        )
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

                        if let metricBarData = metricBarData(for: rule) {
                            metricBar(metricBarData, passed: rule.passed)
                        }

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

    private func metricBar(_ data: RuleMetricBarData, passed: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Metric Bar")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(AppTheme.accentColor)
                Spacer()
                Text(data.legend)
                    .font(.caption)
                    .foregroundStyle(AppTheme.mutedText)
            }

            HStack {
                Spacer(minLength: 0)

                GeometryReader { geometry in
                    let width = max(geometry.size.width, 1)
                    let trackWidth = max(width - 4, 1)
                    let thresholdX = data.thresholdPosition * trackWidth + 2
                    let averageX = data.averagePosition * trackWidth + 2

                    ZStack(alignment: .leading) {
                        Capsule(style: .continuous)
                            .fill(AppTheme.panelBorder.opacity(0.45))
                            .frame(height: 8)

                        markerLabel("T", color: AppTheme.accentColor)
                            .position(x: thresholdX, y: 18)

                        markerLabel(data.averagePosition == data.thresholdPosition ? "*" : "A", color: passed ? AppTheme.success : AppTheme.failure)
                            .position(x: averageX, y: 18)
                    }
                }
                .frame(width: 420, height: 30)

                Spacer(minLength: 0)
            }

            HStack {
                Text(data.metricLine)
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(AppTheme.mutedText)
                Spacer()
            }
        }
        .padding(.top, 4)
    }

    private func markerLabel(_ text: String, color: Color) -> some View {
        Text(text)
            .font(.caption2.weight(.bold))
            .foregroundStyle(.white)
            .frame(width: 18, height: 18)
            .background(Circle().fill(color))
    }

    private func recommendationBadge(_ kind: String) -> some View {
        let text: String
        let color: Color

        switch kind {
        case "blocker":
            text = "BLOCKER"
            color = AppTheme.failure
        case "cost":
            text = "COST"
            color = AppTheme.warning
        default:
            text = "INFO"
            color = AppTheme.success
        }

        return Text(text)
            .font(.caption2.weight(.bold))
            .foregroundStyle(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                Capsule(style: .continuous)
                    .fill(color.opacity(0.12))
            )
    }

    private func metricBarData(for rule: RulePayload) -> RuleMetricBarData? {
        guard
            let metricLabel = rule.metricLabel,
            let averageDetected = rule.averageDetected,
            let threshold = rule.threshold,
            let thresholdKind = rule.thresholdKind,
            thresholdKind == "min" || thresholdKind == "max"
        else {
            return nil
        }

        let upper = max(threshold * 2.0, averageDetected * 1.2, 1.0)
        let thresholdPosition = clamp01(threshold / upper)
        let averagePosition = clamp01(averageDetected / upper)
        let legend = thresholdKind == "min" ? "min-ok >= T" : "max-ok <= T"
        let metricLine = "\(metricLabel): avg=\(formatMetric(averageDetected)) threshold=\(formatMetric(threshold))"
        return RuleMetricBarData(
            thresholdPosition: thresholdPosition,
            averagePosition: averagePosition,
            legend: legend,
            metricLine: metricLine
        )
    }

    private func clamp01(_ value: Double) -> Double {
        min(max(value, 0.0), 1.0)
    }

    private func formatMetric(_ value: Double) -> String {
        value.formatted(.number.precision(.fractionLength(3)))
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

private struct RuleMetricBarData {
    let thresholdPosition: Double
    let averagePosition: Double
    let legend: String
    let metricLine: String
}
