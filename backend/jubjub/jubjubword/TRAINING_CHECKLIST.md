# Hybrid Model Training Checklist

Use this checklist to verify hybrid model training is working correctly.

## Pre-Training Setup

### 1. Environment Setup

```bash
# Verify Python version (3.10+)
python --version

# Create virtual environment (if not exists)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
cd backend
pip install -r requirements.txt

# Verify PyTorch installation
python -c "import torch; print(f'PyTorch {torch.__version__} installed')"
```

**Expected Output**:
```
Python 3.10.x or higher
PyTorch 2.4.1 installed
```

### 2. Database Setup

```bash
# Run migrations
python manage.py migrate

# Load corpora
python manage.py load_corpora --verbosity=2

# Verify corpora exist
python manage.py shell
>>> from jubjub.jubjubword.models import Corpus
>>> print(Corpus.objects.filter(is_active=True).count())
>>> # Should print: 5
>>> for c in Corpus.objects.filter(is_active=True):
...     print(f"{c.slug}: {len(c.get_words_list())} words")
>>> exit()
```

**Expected Output**:
```
5
scifi: 1609 words
fantasy: 1584 words
food: 1541 words
corporate: 1510 words
medical: 1566 words
```

### 3. Markov Models

```bash
# Prebuild Markov models (fast)
python manage.py prebuild_markov_models

# Verify Markov models work
python manage.py shell
>>> from jubjub.jubjubword.markov import get_markov_instance
>>> instance = get_markov_instance(corpus_slug='scifi', n=2, use_word_boundaries=True)
>>> words = instance.genny_batch(count=5)
>>> print(words)
>>> # Should print 5 sci-fi-ish words
>>> exit()
```

**Expected Output**:
```
Building models for 5 corpora...
✓ Built: scifi (n=2, wb=True)
✓ Built: fantasy (n=2, wb=True)
...
['quanticore', 'photonix', 'starforge', 'cyberdyne', 'neurotex']
```

## Training Tests

### 4. Single Corpus Training (Fast Test)

```bash
# Train one corpus with minimal settings (fast test)
python manage.py train_hybrid_models \
  --corpus scifi \
  --hidden-size 32 \
  --epochs 10 \
  --batch-size 16
```

**Expected Duration**: ~1-2 minutes

**Expected Output**:
```
🚀 Training hybrid models for 1 corpora

============================================================
Training: Science Fiction & Tech (scifi)
============================================================

Corpus size: 1609 words

📚 Training LSTM...
Building vocabulary...
Vocabulary size: 32
Train: 1448 words, Val: 161 words
Model parameters: 5,632
Estimated model size: 22.0 KB

Epoch 1/10 - Train Loss: 2.8456, Val Loss: 2.6123
Epoch 2/10 - Train Loss: 2.3145, Val Loss: 2.2456
...

✓ Training complete!
  Epochs trained: 10
  Best val loss: 1.8234
  Final train loss: 1.9012

🔗 Creating hybrid model...
✓ Hybrid model saved to .../hybrid_models/scifi

🎲 Sample generations:
  quanticore (LSTM confidence: 0.58)
  photonix (LSTM confidence: 0.62)
  ...
```

**Verification**:
```bash
# Check files were created
ls -lh jubjub/jubjubword/hybrid_models/scifi/
# Should see:
#   lstm_model.pt (~20-30KB for test)
#   vocabulary.json (~2KB)
#   hybrid_config.json (~200 bytes)
#   best_model.pt (training checkpoint)
#   training_history.json (loss curves)
```

### 5. Model Loading Test

```bash
python manage.py shell
```

```python
from jubjub.jubjubword.hybrid import HybridMarkovLSTM
from jubjub.jubjubword.markov import get_markov_instance
from pathlib import Path

# Load Markov
markov = get_markov_instance(corpus_slug='scifi', n=2, use_word_boundaries=True)
print(f"✓ Markov loaded: {len(markov.transitions)} states")

# Load hybrid
model_dir = Path('jubjub/jubjubword/hybrid_models/scifi')
hybrid = HybridMarkovLSTM.load(model_dir, markov)
print(f"✓ Hybrid loaded")

# Generate words
for i in range(10):
    word, meta = hybrid.generate(max_length=10, temperature=1.0)
    print(f"  {word} (confidence: {meta['avg_lstm_confidence']:.2f})")

print("✓ All tests passed!")
```

**Expected Output**:
```
✓ Markov loaded: 1234 states
✓ Hybrid loaded
  quanticore (confidence: 0.68)
  photonix (confidence: 0.72)
  ...
✓ All tests passed!
```

### 6. Full Training (Production Quality)

```bash
# Train all corpora with production settings
python manage.py train_hybrid_models --all

# Or train individual corpus with optimal settings
python manage.py train_hybrid_models \
  --corpus scifi \
  --hidden-size 64 \
  --num-layers 2 \
  --epochs 50 \
  --batch-size 32 \
  --learning-rate 0.001
```

**Expected Duration**: ~10-15 minutes for all 5 corpora

**File Sizes**:
```bash
ls -lh jubjub/jubjubword/hybrid_models/*/lstm_model.pt

# Expected sizes:
# scifi/lstm_model.pt     ~80KB
# fantasy/lstm_model.pt   ~80KB
# food/lstm_model.pt      ~80KB
# corporate/lstm_model.pt ~80KB
# medical/lstm_model.pt   ~80KB
```

### 7. Evaluation Test

```bash
# Compare hybrid vs pure Markov
python manage.py evaluate_hybrid --corpus scifi --samples 100
```

**Expected Output**:
```
Evaluating Hybrid vs Markov for scifi corpus
Generating 100 samples from each...

Pronounceability Scores:
  Markov:  0.72 ± 0.15
  Hybrid:  0.79 ± 0.12  (+9.7% improvement)

Diversity Metrics:
  Markov:  47 unique character patterns
  Hybrid:  56 unique character patterns  (+19.1% improvement)

LSTM Contribution Analysis:
  Avg LSTM confidence: 0.68
  Avg Markov influence: 0.52
  Avg LSTM influence:   0.48

Sample Comparisons:
  Markov: quanticore, photonix, starforge, ...
  Hybrid: quantumsphere, photonyx, starforged, ...
```

## Common Issues

### Issue: ModuleNotFoundError: No module named 'torch'

**Cause**: PyTorch not installed

**Fix**:
```bash
pip install torch==2.4.1 numpy==1.26.4 tqdm==4.66.1
```

### Issue: Corpus not found

**Cause**: Database not populated

**Fix**:
```bash
python manage.py load_corpora --verbosity=2
```

### Issue: Training very slow

**Possible Causes**:
1. Large batch size on CPU
2. Large model size

**Fix**:
```bash
# Reduce batch size
python manage.py train_hybrid_models --corpus scifi --batch-size 16

# Or reduce model size
python manage.py train_hybrid_models --corpus scifi --hidden-size 32
```

### Issue: Poor generation quality (worse than Markov)

**Possible Causes**:
1. Corpus too small (<500 words)
2. Overfitting (trained too long)
3. Wrong ensemble weights

**Fix**:
```bash
# Reduce epochs to prevent overfitting
python manage.py train_hybrid_models --corpus scifi --epochs 20

# Increase Markov weight
python manage.py train_hybrid_models --corpus scifi \
  --markov-weight 0.7 \
  --lstm-weight 0.3
```

### Issue: FileNotFoundError when loading hybrid

**Cause**: Models not trained or wrong path

**Fix**:
```bash
# Verify model exists
ls jubjub/jubjubword/hybrid_models/scifi/lstm_model.pt

# If missing, train
python manage.py train_hybrid_models --corpus scifi
```

## Success Criteria

### ✅ Training Complete When:

1. **All model files exist**:
   ```bash
   # Should have 3 files per corpus
   ls jubjub/jubjubword/hybrid_models/scifi/
   # lstm_model.pt, vocabulary.json, hybrid_config.json
   ```

2. **Models load without errors**:
   ```python
   hybrid = HybridMarkovLSTM.load(model_dir, markov)
   # No exceptions
   ```

3. **Generation works**:
   ```python
   word, meta = hybrid.generate(max_length=10)
   print(word)  # Real word, not gibberish
   ```

4. **Quality improved**:
   ```bash
   python manage.py evaluate_hybrid --corpus scifi --samples 100
   # Hybrid scores >= Markov scores
   ```

5. **File sizes reasonable**:
   - lstm_model.pt: 50-150KB per corpus
   - Total size: <1MB for all 5 corpora

## Deployment Checklist

### Before Committing Models:

- [ ] All 5 corpora trained
- [ ] Model files verified (<200KB each)
- [ ] Generation quality tested
- [ ] No training checkpoints included (best_model.pt ignored)
- [ ] No training logs included (training_history.json ignored)

### Commit Commands:

```bash
# Check what's being committed
git status jubjub/jubjubword/hybrid_models/

# Should show:
#   new file: scifi/lstm_model.pt
#   new file: scifi/vocabulary.json
#   new file: scifi/hybrid_config.json
#   (repeat for each corpus)

# Should NOT show:
#   best_model.pt (ignored)
#   training_history.json (ignored)

# Add models
git add jubjub/jubjubword/hybrid_models/

# Commit
git commit -m "feat: Add pre-trained hybrid models for all 5 corpora

- Trained with hidden_size=64, num_layers=2, epochs=50
- Models optimized for pronounceability and diversity
- Total size: ~500KB committed
- Deployment-ready (no training needed on Railway)"

# Push
git push origin claude/your-branch
```

### Post-Deployment Verification:

```bash
# After Railway deploys, test the API
curl https://your-app.railway.app/api/generate/scifi/

# Should return generated words (using hybrid if available)
```

## Performance Benchmarks

### Expected Training Times (CPU):

| Corpus    | Words | Hidden Size | Epochs | Time     |
|-----------|-------|-------------|--------|----------|
| scifi     | 1,609 | 64          | 50     | ~3 min   |
| fantasy   | 1,584 | 64          | 50     | ~3 min   |
| food      | 1,541 | 64          | 50     | ~3 min   |
| corporate | 1,510 | 64          | 50     | ~2.5 min |
| medical   | 1,566 | 64          | 50     | ~3 min   |
| **Total** |       |             |        | **15 min** |

### Model Sizes:

| File              | Size   | Description                    |
|-------------------|--------|--------------------------------|
| lstm_model.pt     | ~80KB  | Trained LSTM weights           |
| vocabulary.json   | ~2KB   | Character vocabulary           |
| hybrid_config.json| ~200B  | Ensemble configuration         |
| **Per Corpus**    | **~82KB** | **Total committed**        |
| **All 5 Corpora** | **~410KB** | **Total deployment size** |

### Generation Performance:

- **Pure Markov**: ~0.5-1ms per word
- **Hybrid LSTM**: ~5-10ms per word (10x slower, still fast)
- **Hybrid overhead**: Acceptable for quality improvement

## Next Steps After Training

1. **Commit models** (see commands above)
2. **Push to Railway** (auto-deploys)
3. **Monitor generation** (check pronounceability)
4. **Update corpus** (retrain when adding words)
5. **Evaluate periodically** (ensure quality maintained)

For detailed deployment instructions, see `DEPLOYMENT_HYBRID.md`.
