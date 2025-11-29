import argparse
import sys
from vectalab.core import Vectalab

def main():
    parser = argparse.ArgumentParser(description="Vectalab: Professional SOTA Image Vectorizer")
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("output", help="Path to output SVG")
    parser.add_argument("--model", default="vit_b", help="SAM model type (vit_h, vit_l, vit_b)")
    parser.add_argument("--method", default="sam", choices=["sam", "bayesian"], help="Vectorization method: sam or bayesian")
    parser.add_argument("--device", default="cpu", help="Device to run SAM on (cpu, cuda, mps)")
    parser.add_argument("--points_per_side", type=int, default=32, help="Points per side for SAM grid")
    parser.add_argument("--pred_iou_thresh", type=float, default=0.86, help="IoU threshold")
    parser.add_argument("--stability_score_thresh", type=float, default=0.92, help="Stability score threshold")
    parser.add_argument("--min_mask_region_area", type=int, default=100, help="Minimum mask area")
    parser.add_argument("--turdsize", type=int, default=2, help="Potrace turdsize (despeckle)")
    parser.add_argument("--alphamax", type=float, default=1.0, help="Potrace alphamax (corner threshold)")
    parser.add_argument("--opticurve", action="store_true", default=True, help="Potrace opticurve")
    parser.add_argument("--no-opticurve", action="store_false", dest="opticurve", help="Disable Potrace opticurve")
    
    args = parser.parse_args()
    
    try:
        vm = Vectalab(
            model_type=args.model, 
            device=args.device,
            points_per_side=args.points_per_side,
            pred_iou_thresh=args.pred_iou_thresh,
            stability_score_thresh=args.stability_score_thresh,
            min_mask_region_area=args.min_mask_region_area,
            turdsize=args.turdsize,
            alphamax=args.alphamax,
            opticurve=args.opticurve,
            method=args.method
        )
        vm.vectorize(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
