# Hybrid Model Deployment Guide

## Overview

JubJub Word uses **Option A: Pre-trained Models in Repository** for deploying hybrid Markov-LSTM models. This approach provides:

- **Fast deployment** (<30 seconds startup)
- **Consistent models** across all instances
- **No training overhead** on Railway
- **Predictable behavior** in production

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Railway Deployment                     │
│                                                           │
│  1. Install dependencies (includes PyTorch)             │
│  2. Run migrations                                       │
│  3. Load corpora from database                          │
│  4. Prebuild Markov models (fast)                       │
│  5. Load pre-trained hybrid models from repo            │
│  6. Start gunicorn                                       │
│                                                           │
│  Total Time: ~30 seconds                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   Local Training                         │
│                                                           │
│  When corpora change:                                   │
│  1. Update corpus files                                  │
│  2. Run: python manage.py train_hybrid_models --all     │
│  3. Commit trained models to repo                       │
│  4. Push to trigger Railway deployment                  │
│                                                           │
│  Training Time: ~10-15 minutes (one-time)              │
└─────────────────────────────────────────────────────────┘
```

## Model Storage

### Directory Structure

```
backend/jubjub/jubjubword/
├── hybrid_models/               # Committed to repo
│   ├── scifi/
│   │   ├── lstm_model.pt       # ~80KB (committed)
│   │   ├── vocabulary.json     # ~2KB (committed)
│   │   ├── hybrid_config.json  # ~200B (committed)
│   │   ├── best_model.pt       # Training checkpoint (ignored)
│   │   └── training_history.json # Training log (ignored)
│   ├── fantasy/
│   ├── food/
│   ├── corporate/
│   └── medical/
├── models/                      # Markov models (generated)
│   └── markov_n2_wbTrue_*.pkl  # ~100KB each
└── DEPLOYMENT_HYBRID.md         # This file
```

### What Gets Committed

✅ **Committed** (for fast deployment):
- `lstm_model.pt` - Final trained LSTM (~80KB per corpus)
- `vocabulary.json` - Character vocabulary (~2KB)
- `hybrid_config.json` - Ensemble weights (~200 bytes)

❌ **Ignored** (training artifacts):
- `best_model.pt` - Training checkpoints
- `training_history.json` - Loss curves and metrics

Total committed size: **~500KB for all 5 corpora**

## When to Retrain Models

### Scenarios Requiring Retraining

1. **Adding words to a corpus**
   - Example: Adding 100 new sci-fi words
   - Impact: Hybrid model won't know new vocabulary
   - Action: Retrain affected corpus

2. **Removing words from a corpus**
   - Example: Filtering out inappropriate words
   - Impact: Model may still generate removed patterns
   - Action: Retrain affected corpus

3. **Creating a new corpus**
   - Example: Adding "mythology" corpus
   - Impact: No hybrid model exists
   - Action: Train new corpus

4. **Changing Markov parameters**
   - Example: Switching from n=2 to n=3
   - Impact: State space changed
   - Action: Retrain all corpora

### Scenarios NOT Requiring Retraining

- Changing frontend code
- Updating Django views
- Modifying API endpoints
- Changing ensemble weights (can update hybrid_config.json directly)
- Railway redeployments (models load from repo)

## Training Workflow

### Initial Setup (One-Time)

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Ensure database is populated
python manage.py migrate
python manage.py load_corpora

# 3. Train all hybrid models (takes ~15 minutes)
python manage.py train_hybrid_models --all

# 4. Verify models were created
ls -lh jubjub/jubjubword/hybrid_models/*/lstm_model.pt
# Should see 5 files, ~80KB each

# 5. Commit models to repo
git add jubjub/jubjubword/hybrid_models/
git commit -m "feat: Add pre-trained hybrid models for all corpora"
git push origin claude/your-branch
```

### Updating Existing Corpus

When you modify a corpus (e.g., adding words to sci-fi):

```bash
# 1. Update the corpus in database
python manage.py load_corpora --verbosity=2

# 2. Retrain affected corpus only
python manage.py train_hybrid_models --corpus scifi

# 3. Test generation
python manage.py shell
>>> from jubjub.jubjubword.markov import get_markov_instance
>>> from jubjub.jubjubword.hybrid import HybridMarkovLSTM
>>> from pathlib import Path
>>> markov = get_markov_instance(corpus_slug='scifi')
>>> hybrid = HybridMarkovLSTM.load(Path('jubjub/jubjubword/hybrid_models/scifi'), markov)
>>> word, meta = hybrid.generate(max_length=10)
>>> print(f"Generated: {word}")

# 4. Commit and push
git add jubjub/jubjubword/hybrid_models/scifi/
git commit -m "feat: Retrain sci-fi hybrid model with expanded corpus"
git push origin claude/your-branch
```

### Adding New Corpus

When adding a completely new corpus:

```bash
# 1. Create corpus in database (via admin or migration)
# ...

# 2. Train model for new corpus
python manage.py train_hybrid_models --corpus mythology

# 3. Commit new model directory
git add jubjub/jubjubword/hybrid_models/mythology/
git commit -m "feat: Add hybrid model for mythology corpus"
git push origin claude/your-branch
```

## Training Options

### Basic Training

```bash
# Train all corpora with defaults
python manage.py train_hybrid_models --all

# Train specific corpus
python manage.py train_hybrid_models --corpus scifi
```

### Advanced Options

```bash
# Larger model for better quality (takes longer)
python manage.py train_hybrid_models --corpus scifi \
  --hidden-size 128 \
  --num-layers 3 \
  --epochs 100

# Faster training for testing
python manage.py train_hybrid_models --corpus scifi \
  --hidden-size 32 \
  --epochs 20

# Adjust ensemble weights
python manage.py train_hybrid_models --corpus scifi \
  --markov-weight 0.7 \
  --lstm-weight 0.3

# GPU training (if available)
python manage.py train_hybrid_models --corpus scifi --device cuda
```

### Training Output

Expect to see:

```
🚀 Training hybrid models for 1 corpora

Hyperparameters:
  Hidden size: 64
  Num layers: 2
  Epochs: 50
  Batch size: 32
  Learning rate: 0.001
  Device: cpu
  Markov weight: 0.6
  LSTM weight: 0.4

============================================================
Training: Science Fiction & Tech (scifi)
============================================================

Corpus size: 1609 words

📚 Training LSTM...
Building vocabulary...
Vocabulary size: 32
Train: 1448 words, Val: 161 words
Model parameters: 21,024
Estimated model size: 82.1 KB

Epoch 1/50 - Train Loss: 2.8456, Val Loss: 2.6123
Epoch 2/50 - Train Loss: 2.3145, Val Loss: 2.2456
...
Early stopping triggered after 35 epochs

✓ Training complete!
  Epochs trained: 35
  Best val loss: 1.4523
  Final train loss: 1.5012

🔗 Creating hybrid model...
✓ Hybrid model saved to .../hybrid_models/scifi

🎲 Sample generations:
  quanticore (LSTM confidence: 0.68)
  photonix (LSTM confidence: 0.72)
  starforge (LSTM confidence: 0.65)
  cyberdyne (LSTM confidence: 0.71)
  neurotex (LSTM confidence: 0.69)

🎉 Training complete! Models saved to .../hybrid_models
```

## Evaluation

### Compare Hybrid vs Pure Markov

```bash
python manage.py evaluate_hybrid --corpus scifi --samples 100
```

Expected improvements:
- **Pronounceability**: +5-15% (more phonetically natural)
- **Diversity**: +10-20% (unique character patterns)
- **Consistency**: Similar (both respect corpus style)

### Detailed Analysis

```bash
# Generate comparison report
python manage.py evaluate_hybrid --corpus scifi --samples 500 --report

# Output saved to: jubjub/jubjubword/evaluation_reports/scifi_evaluation.json
```

## Railway Configuration

### Current Setup (No Changes Needed)

`railway.json` already includes Markov model prebuilding:

```json
{
  "deploy": {
    "startCommand": "python manage.py migrate && python manage.py load_corpora --verbosity=2 && python manage.py prebuild_markov_models && gunicorn jubjub.wsgi:application --bind 0.0.0.0:$PORT"
  }
}
```

**Why we DON'T add hybrid training:**
- Hybrid models are pre-trained and committed to repo
- Railway loads models from disk (fast)
- No training needed on deployment (saves 10-15 minutes)
- Deployment stays under 1 minute

### What Railway Does

1. **Pulls repo** (includes pre-trained hybrid models)
2. **Installs PyTorch** (~200MB, used for inference only)
3. **Runs migrations** (sets up database)
4. **Loads corpora** (populates word lists)
5. **Prebuilds Markov models** (fast, ~1 second per corpus)
6. **Starts gunicorn** (hybrid models auto-load when requested)

### Environment Variables (Optional)

If you want to disable hybrid models temporarily:

```bash
# Railway dashboard -> Environment Variables
ENABLE_HYBRID_MODELS=false
```

Then update `views.py` to check this flag.

## Troubleshooting

### Models Not Loading

**Symptom**: `FileNotFoundError: hybrid_models/scifi/lstm_model.pt not found`

**Fix**:
```bash
# Verify models exist in repo
ls backend/jubjub/jubjubword/hybrid_models/*/lstm_model.pt

# If missing, train locally
python manage.py train_hybrid_models --all

# Commit and push
git add jubjub/jubjubword/hybrid_models/
git commit -m "fix: Add missing hybrid models"
git push
```

### Poor Generation Quality

**Symptom**: Hybrid generates worse words than pure Markov

**Possible Causes**:
1. **Corpus too small** (<500 words) - LSTM can't learn patterns
2. **Overfitting** - LSTM memorized training data
3. **Bad weights** - Ensemble favoring wrong model

**Fix**:
```bash
# Retrain with early stopping and more validation data
python manage.py train_hybrid_models --corpus scifi --epochs 30

# Or adjust ensemble weights (more Markov, less LSTM)
python manage.py train_hybrid_models --corpus scifi \
  --markov-weight 0.8 \
  --lstm-weight 0.2
```

### Slow Deployment

**Symptom**: Railway deployment takes >5 minutes

**Possible Causes**:
1. PyTorch installation slow (normal first time)
2. Accidentally training models on Railway (check railway.json)

**Fix**:
```bash
# Verify railway.json does NOT include training
cat backend/railway.json | grep train_hybrid

# Should return nothing - training is NOT in startCommand
```

### Large Repository Size

**Symptom**: Git repo over 100MB

**Possible Causes**:
1. Committing training checkpoints (best_model.pt)
2. Committing training history (training_history.json)

**Fix**:
```bash
# Remove ignored files from git
git rm --cached backend/jubjub/jubjubword/hybrid_models/*/best_model.pt
git rm --cached backend/jubjub/jubjubword/hybrid_models/*/training_history.json

# Verify .gitignore includes them
cat .gitignore | grep hybrid_models
```

## Monitoring

### Check Model Status

```python
# In Django shell
from jubjub.jubjubword.hybrid import HybridMarkovLSTM
from jubjub.jubjubword.markov import get_markov_instance
from pathlib import Path
import os

# Check which models exist
models_dir = Path('jubjub/jubjubword/hybrid_models')
available = [d.name for d in models_dir.iterdir() if d.is_dir()]
print(f"Available hybrid models: {available}")

# Load and test
markov = get_markov_instance(corpus_slug='scifi')
hybrid = HybridMarkovLSTM.load(models_dir / 'scifi', markov)

# Generate with metadata
word, meta = hybrid.generate(max_length=10)
print(f"Word: {word}")
print(f"LSTM confidence: {meta['avg_lstm_confidence']:.2f}")
print(f"Markov influence: {meta['avg_markov_influence']:.2f}")
print(f"LSTM influence: {meta['avg_lstm_influence']:.2f}")
```

### Performance Metrics

```bash
# Generate 1000 words and analyze
python manage.py evaluate_hybrid --corpus scifi --samples 1000 --report

# Check pronounceability distribution
# Check diversity metrics
# Compare to pure Markov baseline
```

## Future Enhancements

### Option B: Train on Deployment (If Needed)

If corpora become dynamic (user-contributed words), switch to Option B:

**railway.json** change:
```json
{
  "deploy": {
    "startCommand": "python manage.py migrate && python manage.py load_corpora --verbosity=2 && python manage.py prebuild_markov_models && python manage.py train_hybrid_models --all --epochs 30 && gunicorn jubjub.wsgi:application --bind 0.0.0.0:$PORT"
  }
}
```

**Tradeoffs**:
- ✅ Always fresh models
- ❌ 10-15 minute deployment time
- ❌ Higher compute costs

### Git LFS (If Models Exceed 100MB)

If you add many more corpora:

```bash
# Install Git LFS
git lfs install

# Track model files
git lfs track "*.pt"
git lfs track "*.pkl"

# Update .gitattributes (already configured)
```

### Incremental Training

Future feature to update models without full retrain:

```python
# Add new words to existing model
from jubjub.jubjubword.hybrid_trainer import incremental_train

incremental_train(
    corpus_slug='scifi',
    new_words=['quantumflux', 'nanocore', 'cyberdeck'],
    epochs=10  # Fine-tune only
)
```

## Summary

**Current Setup (Option A)**:
- ✅ Pre-trained models committed to repo
- ✅ Fast Railway deployments (<1 minute)
- ✅ No training overhead in production
- ✅ ~500KB model size (acceptable)

**When corpora change**:
- Train locally: `python manage.py train_hybrid_models --corpus X`
- Commit models: `git add hybrid_models/X/ && git commit`
- Deploy: `git push` (Railway auto-deploys)

**Maintenance**:
- Retrain when corpus words change
- ~15 minutes total training time (infrequent)
- Models stay in sync with corpus content

This approach balances simplicity, performance, and maintainability for JubJub Word's current scale.
