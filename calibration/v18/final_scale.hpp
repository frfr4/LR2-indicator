#pragma once

#include <algorithm>
#include <cmath>

namespace chart_radar {

struct FinalRatingTail {
    double thousandPointThreshold;
    double sampleMaximum;
    double upperSlope;
};

inline constexpr FinalRatingTail notesTail{1205.095, 1287.57, 2.70650500152};
inline constexpr FinalRatingTail chordTail{1168.47, 1226.51, 3.53034114404};
inline constexpr FinalRatingTail peakTail{942.74, 957.93, 4.0};

// Input is the fully scored v17 skill, including its original pattern modifiers.
inline double finalRating(double score, const FinalRatingTail& tail)
{
    constexpr double start = 800.0;
    if (score <= start)
        return score;

    if (score <= tail.thousandPointThreshold) {
        const double progress = (score - start) / (tail.thousandPointThreshold - start);
        return start + (1000.0 - start) * progress;
    }

    const double linearEnd = std::min(score, tail.sampleMaximum);
    const double mapped = 1000.0 + (linearEnd - tail.thousandPointThreshold) * tail.upperSlope;
    if (score <= tail.sampleMaximum)
        return mapped;

    // Continue past the reference population without a hard ceiling.
    constexpr double tailScale = 100.0;
    const double excess = (score - tail.sampleMaximum) * tail.upperSlope;
    return mapped + tailScale * std::log1p(excess / tailScale);
}

// Apply once after all non-stamina skills, then run the existing stamina support loop.
// Pass native skill references in named order; the TSV and radial display orders differ.
inline void applyFinalSkillRatings(double& notes, double& chord, double& peak)
{
    notes = finalRating(notes, notesTail);
    chord = finalRating(chord, chordTail);
    peak = finalRating(peak, peakTail);
}

} // namespace chart_radar
