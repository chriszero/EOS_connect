# EOS Connect Documentation

This directory contains the GitHub Pages documentation for EOS Connect.

## 🌐 Live Documentation

The documentation is published at: **https://ohAnd.github.io/EOS_connect/**

## 📁 Structure

```
docs/
├── index.html                  # Homepage with 4-section overview
├── _config.yml                 # Jekyll configuration
├── .nojekyll                   # Skip Jekyll processing for certain files
├── assets/
│   └── css/
│       └── style.css          # Custom CSS matching app design
├── what-is/
│   └── index.html             # Section 1: What is EOS Connect
├── user-guide/
│   └── index.html             # Section 2: User Guide (installation, config)
├── advanced/
│   └── index.html             # Section 3: Advanced (API, MQTT, automation)
└── developer/
    └── index.html             # Section 4: Developer Guide (architecture, contributing)
```

## 🎨 Design

The documentation uses custom HTML/CSS matching the EOS Connect application design:
- Dark theme (matching app's color scheme)
- Responsive layout
- Modern, clean interface
- Easy navigation with 4 main sections

## 🔧 Local Development

To test the documentation locally:

### Option 1: Simple HTTP Server
```bash
cd docs
python -m http.server 8000
# Visit http://localhost:8000
```

### Option 2: Jekyll (if installed)
```bash
cd docs
jekyll serve
# Visit http://localhost:4000/EOS_connect/
```

## 📝 Editing Documentation

### Adding New Pages
1. Create HTML file in appropriate section folder
2. Use the same header/footer structure for consistency
3. Link stylesheet: `<link rel="stylesheet" href="../assets/css/style.css">`
4. Update navigation in index.html if needed

### Updating Styles
Edit `assets/css/style.css` - changes apply to all pages.

Key CSS classes:
- `.hero` - Page header sections
- `.content-section` - Main content blocks
- `.block-card` - Navigation cards
- `.feature-grid` - Feature list grid
- `.alert` - Info/warning/success boxes

### Content Guidelines
- Keep content user-focused
- Use examples where possible
- Link between related pages
- Maintain consistent formatting
- Update both GitHub Pages and main README.md when needed

## 🚀 Publishing

GitHub Pages automatically publishes from the `docs/` folder when changes are pushed to the main branch.

To enable GitHub Pages:
1. Go to repository Settings → Pages
2. Set Source to "Deploy from a branch"
3. Select branch: `main` (or `develop`)
4. Set folder: `/docs`
5. Save

Changes will be live within a few minutes.

## 📦 Included Sections

### 1. What is EOS Connect (`what-is/`)
- Introduction and overview
- How it works
- Core features (battery, solar, cost optimization)
- Integration capabilities
- Benefits summary

### 2. User Guide (`user-guide/`)
- Quick start
- Installation methods (HA, Docker, local)
- Configuration overview
- Using the web dashboard
- Common tasks
- EOS server setup

### 3. Advanced Features (`advanced/`)
- REST API reference
- MQTT integration
- External integrations (HA, OpenHAB, EVCC, Fronius)
- Automation examples
- Advanced configuration

### 4. Developer Guide (`developer/`)
- Architecture overview
- Contributing guidelines
- Testing procedures
- Development setup
- Project structure
- Resources

## 🔗 Relationship to Main README

The main `README.md` in the repository root is now condensed and links to this comprehensive GitHub Pages documentation:

- **README.md** (~150 lines): Quick overview, basic setup, links to docs
- **GitHub Pages** (full docs): Comprehensive guides, API reference, examples

This separation provides:
- ✅ Clean GitHub repository landing page
- ✅ Professional, searchable documentation site
- ✅ Better user experience
- ✅ Easier maintenance

## 📄 Files Created

New condensed files (to replace existing):
- `README_NEW.md` → Should replace `README.md`
- `src/CONFIG_README_NEW.md` → Should replace `src/CONFIG_README.md`

## 🛠️ Next Steps

1. Review the generated documentation
2. Test locally using `python -m http.server 8000`
3. Replace old README files with new condensed versions:
   - `mv README_NEW.md README.md`
   - `mv src/CONFIG_README_NEW.md src/CONFIG_README.md`
4. Commit and push to repository
5. Enable GitHub Pages in repository settings
6. Share the documentation link!

## 💡 Maintenance Tips

- Keep documentation in sync with code changes
- Update version numbers when releasing
- Add examples for new features
- Respond to documentation issues/PRs
- Periodically review for outdated content

---

**Questions or suggestions?** Open an issue or discussion on GitHub!
