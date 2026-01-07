# EOS Connect Documentation

This directory contains the GitHub Pages documentation for EOS Connect.

## 🌐 Live Documentation

The documentation is published at: **https://ohAnd.github.io/EOS_connect/**

## 📁 Structure

```
docs/
├── index.html                  # Homepage with overview and navigation
├── _config.yml                 # Jekyll configuration
├── .nojekyll                   # Skip Jekyll processing
├── README.md                   # This file
├── assets/
│   ├── css/
│   │   └── style.css          # Custom CSS matching app design
│   ├── images/                # Documentation images (icon, logo, screenshots)
│   ├── includes/              # Template partials (header, footer)
│   └── js/
│       └── common.js          # Shared JavaScript functionality
├── what-is/
│   └── index.html             # Section 1: What is EOS Connect
├── user-guide/
│   ├── index.html             # Section 2: User Guide (installation)
│   └── configuration.html     # Configuration reference (all parameters)
├── advanced/
│   └── index.html             # Section 3: Advanced (API, MQTT, automation)
└── developer/
    └── index.html             # Section 4: Developer Guide (architecture, contributing)
```

## 🎨 Design

The documentation uses custom HTML/CSS matching the EOS Connect application design:
- Dark theme (matching app's color scheme: rgb(54, 54, 54))
- Responsive layout with mobile hamburger menu
- Sticky navigation header and table of contents
- Back-to-top button for easy navigation
- Modern, clean interface
- FontAwesome icons throughout
- Draft banner overlay (removable when finalized)

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
- `.feature-grid` - Feature list grid (responsive)
- `.alert` - Info/warning/success boxes
- `.nav-header` - Sticky navigation bar
- `.toc-sidebar` - Table of contents sidebar
- `.back-to-top` - Back to top button
- `.draft-banner` - Draft watermark overlay
- `.mobile-menu-toggle` - Mobile menu button

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
- EOS/EVopt server setup
- Configuration reference (`configuration.html`)
  - All config.yaml parameters documented
  - Load, battery, PV forecast settings
  - Price integration options
  - Inverter and EVCC configuration
  - MQTT settings
- Using the web dashboard
- Common tasks

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

The main `README.md` and `src/CONFIG_README.md` in the repository root have been streamlined to link to this comprehensive GitHub Pages documentation:

- **README.md** (root): Quick overview, basic setup, links to full docs
- **src/CONFIG_README.md**: Minimal config example, links to configuration.html
- **GitHub Pages** (full docs): Comprehensive guides, API reference, all parameters

This separation provides:
- ✅ Clean GitHub repository landing page
- ✅ Professional, searchable documentation site
- ✅ Better user experience for new and existing users
- ✅ Easier maintenance (single source of truth for detailed docs)
- ✅ Sponsorship integration throughout

## 📄 Key Features

Current documentation includes:
- **Sponsorship links**: GitHub Sponsors integrated in header (coffee icon) and footer
- **Mobile responsive**: Hamburger menu for screens <768px
- **Back-to-top button**: Appears after scrolling 300px
- **EVopt links**: Correct repository (thecem/hassio-evopt) referenced
- **Temperature protection**: Battery charging curve details with temperature tables
- **Configuration tables**: Standardized 200px width for parameter names
- **Draft mode**: Visible banner for review phase (easy to remove)

## 🛠️ Next Steps

### Before Publishing:
1. **Remove draft banner**: Delete the draft banner section from all pages when ready
2. **Test locally**: Use `python -m http.server 8000` to verify all pages
3. **Check mobile view**: Test responsive design on narrow screens
4. **Verify links**: Ensure all internal and external links work
5. **Review content**: Check for typos, outdated information, accuracy

### Publishing:
1. Commit and push to repository (develop or main branch)
2. Enable GitHub Pages in repository settings
3. Set Source to "Deploy from a branch"
4. Select branch and set folder to `/docs`
5. Wait a few minutes for deployment
6. Share the documentation link: https://ohAnd.github.io/EOS_connect/

### After Publishing:
1. Monitor GitHub Issues for documentation feedback
2. Update when new features are added
3. Keep synchronization between README_new.md files and this documentation

## 💡 Maintenance Tips

- Keep documentation in sync with code changes
- Update version numbers when releasing
- Add examples for new features
- Respond to documentation issues/PRs
- Periodically review for outdated content

---

**Questions or suggestions?** Open an issue or discussion on GitHub!
