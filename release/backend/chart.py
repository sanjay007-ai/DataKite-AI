"""Compatibility chart helpers for the dashboard backend."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def line_chart(labels, values, title="Sales Trend", path=None):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(labels, values, marker="o")
    ax.set_title(title)
    ax.grid(True, alpha=.2)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        return path
    return fig
