import { Component, type ReactNode } from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[400px] flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <AlertTriangle className="w-8 h-8 text-signal-amber mx-auto mb-4" />
            <h2 className="font-serif text-lg text-text-primary italic mb-2">Something went wrong</h2>
            <p className="font-mono text-[11px] text-text-muted mb-4 break-all">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <button
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 px-4 py-2 bg-surface hover:bg-surface-hover border border-border rounded font-mono text-[11px] text-text-secondary hover:text-text-primary uppercase tracking-wider transition-all"
            >
              <RotateCw className="w-3 h-3" />
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
