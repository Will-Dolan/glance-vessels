import { mapState } from 'vuex';

const FILE_TYPES = ['.png', '.jpeg', '.gif'];

// ----------------------------------------------------------------------------
// Component API
// ----------------------------------------------------------------------------

function generateImage() {
  const img = new Image();
  img.addEventListener('load', () => {
    const ctx = this.canvas.getContext('2d');
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    this.canvas.width = img.width;
    this.canvas.height = img.height;

    if (!this.transparentBackground) {
      ctx.fillStyle = this.backgroundToFillStyle(
        this.screenshot.viewData.background
      );
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    ctx.drawImage(img, 0, 0);

    const imageType = `image/${this.fileType.substr(1)}`;
    this.imageUrl = this.canvas.toDataURL(imageType);
  });

  img.src = this.screenshot.imgSrc;
}

// ----------------------------------------------------------------------------

function backgroundToFillStyle(bg) {
  if (bg.startsWith('linear-gradient(')) {
    // parse out linear gradient, assumed to be top-bottom
    const stops = bg.substring(bg.indexOf('(') + 1, bg.indexOf(')')).split(',');

    const ctx = this.canvas.getContext('2d');
    // top to bottom
    const gradient = ctx.createLinearGradient(0, 0, 0, this.canvas.height);
    gradient.addColorStop(0, stops[0]);
    gradient.addColorStop(1, stops[1]);
    return gradient;
  }
  // we currently don't handle images or any other background value
  return bg;
}

// ----------------------------------------------------------------------------

function save() {
  this.$emit('save', this.screenshot.viewName, {
    image: this.imageUrl,
    filename: this.filename + this.fileType,
  });
}

// ----------------------------------------------------------------------------

export default {
  name: 'ScreenshotDialog',
  data() {
    return {
      filename: '',
      imageUrl: '',
      transparentBackground: false,
      fileType: '',
      fileTypes: FILE_TYPES,
    };
  },
  computed: mapState('screenshots', {
    screenshot: 'currentScreenshot',
    showDialog: 'showDialog',
  }),
  watch: {
    transparentBackground: generateImage,
    showDialog(val) {
      if (val) {
        this.filename = 'Untitled';
        this.fileType = '.png';
        this.generateImage();
      }
    },
  },
  methods: {
    generateImage,
    backgroundToFillStyle,
    save,
    close() {
      this.$store.commit('screenshots/closeDialog');
    },
  },
  created() {
    this.canvas = document.createElement('canvas');
  },
};
