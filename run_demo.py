from src.actions import generate_actions
from src.data import synthetic_bundle
from src.ranking import rank_candidates
from src.state import AnalysisState


def main() -> None:
    state = AnalysisState()
    bundle = synthetic_bundle()
    print("当前状态:", state.to_dict())
    for i, candidate in enumerate(rank_candidates(bundle, state, generate_actions(state))[:3], 1):
        print(f"{i}. {candidate.action.label} | score={candidate.score:.3f} | {candidate.reason}")


if __name__ == "__main__":
    main()
